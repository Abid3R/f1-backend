from fastapi import APIRouter
from pydantic import BaseModel, Field
from pathlib import Path
from typing import List, Literal, Optional
import joblib
import pandas as pd
import numpy as np

from services.strategy_engine import (
    StintPlan,
    find_best_pit_window,
    predict_qualifying_top5,
    simulate_strategy,
)

router = APIRouter()

# ── Load model artifacts once at startup ─────────────────────────────────────
_BASE = Path(__file__).resolve().parent.parent   # points to f1-backend/

_model     = joblib.load(_BASE / "pitstop_model.pkl")
_threshold = float(joblib.load(_BASE / "pitstop_threshold.pkl"))
_features  = joblib.load(_BASE / "pitstop_features.pkl")

# Tyre compound → ordinal (must match training encoding)
_COMPOUND_ORD = {"SOFT": 0, "MEDIUM": 1, "HARD": 2, "INTERMEDIATE": 3, "WET": 4}


# ── Request schema ────────────────────────────────────────────────────────────
class PitStopInput(BaseModel):
    driver: str
    race: str
    compound: str
    lap_number: int
    tyre_life: int
    position: int
    lap_time_delta: float
    cumulative_degradation: float
    race_progress: float
    position_change: int


# ── Feature engineering (mirrors training pipeline) ───────────────────────────
def _build_features(data: PitStopInput) -> pd.DataFrame:
    compound     = data.compound.upper()
    compound_ord = float(_COMPOUND_ORD.get(compound, 1))
    tl           = float(data.tyre_life)
    ln           = float(data.lap_number)
    rp           = float(data.race_progress)
    pos          = float(data.position)
    delta        = float(data.lap_time_delta)
    cum_deg      = float(data.cumulative_degradation)

    # Estimate stint number from lap/tyre-life ratio
    stint = float(max(1, round(ln / max(tl, 1))))

    row = {
        "LapNumber":               ln,
        "Stint":                   stint,
        "TyreLife":                tl,
        "Position":                pos,
        "LapTime (s)":             90.0,       # default; delta is the predictive signal
        "LapTime_Delta":           delta,
        "Cumulative_Degradation":  cum_deg,
        "RaceProgress":            rp,
        "Position_Change":         float(data.position_change),
        "PitStop":                 0.0,        # predicting future pit, not current
        # Categorical encodings (0 = unknown driver/race — safe default for LightGBM)
        "Compound_ord":            compound_ord,
        "Driver_enc":              0.0,
        "Race_enc":                0.0,
        # Engineered features
        "TyreLife_sq":             tl ** 2,
        "TyreLife_high":           float(tl > 25),
        "TyreLife_critical":       float(tl > 35),
        "TyreLife_norm":           tl / (ln + 1),
        "is_early_race":           float(rp < 0.25),
        "is_mid_race":             float(0.25 <= rp < 0.75),
        "is_late_race":            float(rp >= 0.75),
        "TyreLife_x_Compound":     tl * compound_ord,
        "Degradation_per_lap":     cum_deg / (tl + 1),
        "Position_x_Progress":     pos * rp,
        "Delta_x_TyreLife":        delta * tl,
        "AbsDelta_x_TyreLife":     abs(delta) * tl,
        "just_pitted":             0.0,
    }

    return pd.DataFrame([row])[_features]


# ── Human-readable analysis bullets ──────────────────────────────────────────
def _generate_reasons(data: PitStopInput, prob: float) -> list[str]:
    reasons: list[str] = []
    compound = data.compound.upper()

    # Tyre age
    if data.tyre_life >= 35:
        reasons.append(
            f"Critical tyre age: {data.tyre_life} laps — severely worn, pit overdue."
        )
    elif data.tyre_life >= 25:
        reasons.append(
            f"High tyre age: {data.tyre_life} laps — deep inside the pit window."
        )
    elif data.tyre_life >= 15:
        reasons.append(
            f"Moderate tyre age: {data.tyre_life} laps — approaching the pit window."
        )
    else:
        reasons.append(
            f"Fresh tyres: only {data.tyre_life} laps on this set — unlikely to pit."
        )

    # Compound
    if compound == "SOFT":
        reasons.append("Soft compound degrades quickly — increases pit urgency.")
    elif compound == "HARD":
        reasons.append("Hard compound allows extended stints — reduces pit urgency.")
    elif compound in ("INTERMEDIATE", "WET"):
        reasons.append("Weather tyre — strategy may change with track conditions.")

    # Lap time degradation
    if data.lap_time_delta >= 1.5:
        reasons.append(
            f"Significant pace loss: +{data.lap_time_delta:.2f}s vs baseline — tyres fading."
        )
    elif data.lap_time_delta >= 0.5:
        reasons.append(
            f"Lap time slowing: +{data.lap_time_delta:.2f}s — visible degradation."
        )
    elif data.lap_time_delta < -0.5:
        reasons.append(
            f"Lap time improving: {data.lap_time_delta:.2f}s — tyres still performing well."
        )

    # Cumulative degradation
    if data.cumulative_degradation >= 4.0:
        reasons.append(
            f"Severe cumulative degradation: {data.cumulative_degradation:.1f}s total lost."
        )
    elif data.cumulative_degradation >= 2.0:
        reasons.append(
            f"Cumulative degradation building: {data.cumulative_degradation:.1f}s total."
        )

    # Race phase
    pct = round(data.race_progress * 100)
    if data.race_progress < 0.25:
        reasons.append(f"Early race ({pct}% complete) — under-cut window may open soon.")
    elif data.race_progress >= 0.75:
        reasons.append(f"Late race ({pct}% complete) — tyre management crucial for finish.")
    else:
        reasons.append(f"Race is {pct}% complete — standard pit-stop window.")

    # Position context
    if data.position_change < -1:
        reasons.append(
            f"Losing {abs(data.position_change)} place(s) — pit stop may recover track position."
        )
    elif data.position_change > 1:
        reasons.append(
            f"Gaining {data.position_change} place(s) on raw pace — pit stop would surrender this."
        )

    return reasons[:4]   # cap at 4 for clean UI display


# ── Endpoint (same URL as before — frontend unchanged) ────────────────────────
@router.post("/pitstop-demo")
def predict_pitstop(data: PitStopInput):
    X        = _build_features(data)
    prob     = float(_model.predict_proba(X)[0][1])
    will_pit = prob >= _threshold
    reasons  = _generate_reasons(data, prob)

    return {
        "driver":      data.driver,
        "race":        data.race,
        "will_pit":    will_pit,
        "probability": round(prob, 4),
        "percentage":  round(prob * 100, 1),
        "compound":    data.compound.upper(),
        "reason":      reasons,
    }


# ── /predict/strategy ─────────────────────────────────────────────────────────
class StintIn(BaseModel):
    compound: Literal["SOFT", "MEDIUM", "HARD", "INTERMEDIATE", "WET"]
    laps: int = Field(..., ge=1, le=80)


class StrategyInput(BaseModel):
    base_pace: float = Field(90.0, gt=30, lt=180, description="Reference clean-air lap time (s)")
    total_laps: int = Field(..., ge=10, le=80)
    stints: List[StintIn] = Field(..., min_length=1, max_length=4)
    starting_fuel_kg: float = Field(110.0, ge=20, le=130)
    fuel_consumption_per_lap: float = Field(1.9, ge=0.5, le=4.0)
    optimize_pit_window: bool = False
    starting_compound: Optional[str] = None
    second_compound: Optional[str] = None


@router.post("/strategy")
def predict_strategy(data: StrategyInput):
    """
    Simulate a full race strategy: per-lap times under tyre deg + fuel burn.
    Optionally, return the optimal 1-stop pit window across `starting_compound`
    → `second_compound`.
    """
    sim = simulate_strategy(
        base_pace=data.base_pace,
        total_laps=data.total_laps,
        stints=[StintPlan(s.compound, s.laps) for s in data.stints],
        starting_fuel_kg=data.starting_fuel_kg,
        fuel_consumption_per_lap=data.fuel_consumption_per_lap,
    )

    optimal = None
    if data.optimize_pit_window and data.starting_compound and data.second_compound:
        optimal = find_best_pit_window(
            base_pace=data.base_pace,
            total_laps=data.total_laps,
            starting_compound=data.starting_compound.upper(),     # type: ignore[arg-type]
            second_compound=data.second_compound.upper(),         # type: ignore[arg-type]
        )

    return {**sim, "optimal_pit_window": optimal}


# ── /predict/qualifying ───────────────────────────────────────────────────────
class QualiSample(BaseModel):
    driver_number: int
    name: str
    team_colour: Optional[str] = None
    fp1_best: float = 90.0
    fp2_best: float = 90.0
    fp3_best: float = 90.0
    fuel_kg: float = 0.0
    long_run_avg: float = 0.0


class QualifyingInput(BaseModel):
    samples: List[QualiSample] = Field(..., min_length=2, max_length=20)


@router.post("/qualifying")
def predict_qualifying(data: QualifyingInput):
    """Fuel-corrected FP1/FP2/FP3 micro-sector blend → projected top-5 grid."""
    payload = [s.model_dump() for s in data.samples]
    return {"top_5": predict_qualifying_top5(payload)}
