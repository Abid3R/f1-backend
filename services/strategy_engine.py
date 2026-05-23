"""
Lightweight, pandas-friendly strategy simulator.

This is intentionally a *physically-motivated heuristic*, not a deep ML model:
- tyre lap time = base_pace + degradation * (lap_age ** deg_exp) + fuel_penalty * remaining_fuel
- pit window = arg-min over candidate pit laps of total race time
- output: per-strategy lap times, expected pit window, total race time

We expose two endpoints:
- /api/predict/strategy
- /api/predict/qualifying
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np
import pandas as pd

Compound = Literal["SOFT", "MEDIUM", "HARD", "INTERMEDIATE", "WET"]

# Approximate 2024/2025 dry compound profile (seconds vs medium reference)
# pace_delta < 0 means faster than medium baseline.
COMPOUND_PROFILE: dict[str, dict[str, float]] = {
    "SOFT":   {"pace_delta": -0.45, "deg":  0.060, "deg_exp": 1.55, "max_life": 22},
    "MEDIUM": {"pace_delta":  0.00, "deg":  0.035, "deg_exp": 1.45, "max_life": 32},
    "HARD":   {"pace_delta": +0.35, "deg":  0.022, "deg_exp": 1.35, "max_life": 45},
    "INTERMEDIATE": {"pace_delta": +2.5, "deg": 0.015, "deg_exp": 1.20, "max_life": 30},
    "WET":          {"pace_delta": +6.0, "deg": 0.012, "deg_exp": 1.15, "max_life": 25},
}

# typical pit lane loss in seconds (delta time vs not pitting)
PIT_LOSS_SECONDS = 22.0


@dataclass
class StintPlan:
    compound: Compound
    laps: int


def simulate_stint(
    base_pace: float,
    compound: Compound,
    laps: int,
    *,
    start_age: int = 0,
    fuel_penalty_per_kg: float = 0.035,
    starting_fuel_kg: float = 110.0,
    fuel_consumption_per_lap: float = 1.9,
    lap_offset: int = 0,
) -> list[float]:
    """Return a list of lap times for a single stint."""
    profile = COMPOUND_PROFILE[compound]
    lap_times: list[float] = []
    for i in range(laps):
        age = start_age + i + 1
        deg = profile["deg"] * (age ** profile["deg_exp"])
        fuel = max(0.0, starting_fuel_kg - (lap_offset + i) * fuel_consumption_per_lap)
        fuel_pen = fuel * fuel_penalty_per_kg
        lap_times.append(base_pace + profile["pace_delta"] + deg + fuel_pen)
    return lap_times


def simulate_strategy(
    *,
    base_pace: float,
    total_laps: int,
    stints: list[StintPlan],
    starting_fuel_kg: float = 110.0,
    fuel_consumption_per_lap: float = 1.9,
) -> dict:
    """Return per-lap time DataFrame + summary stats for a given strategy."""
    rows: list[dict] = []
    cursor = 0
    for idx, stint in enumerate(stints):
        lap_times = simulate_stint(
            base_pace,
            stint.compound,
            stint.laps,
            starting_fuel_kg=starting_fuel_kg,
            fuel_consumption_per_lap=fuel_consumption_per_lap,
            lap_offset=cursor,
        )
        for j, t in enumerate(lap_times):
            rows.append({"lap": cursor + j + 1, "stint": idx + 1, "compound": stint.compound, "lap_time": t})
        cursor += stint.laps

    # Append pit losses
    total_time = sum(r["lap_time"] for r in rows) + PIT_LOSS_SECONDS * (len(stints) - 1)

    df = pd.DataFrame(rows)
    df = df[df["lap"] <= total_laps]  # truncate
    return {
        "laps": df.to_dict(orient="records"),
        "total_time_seconds": round(total_time, 2),
        "stint_count": len(stints),
        "pit_count": max(0, len(stints) - 1),
    }


def find_best_pit_window(
    *,
    base_pace: float,
    total_laps: int,
    starting_compound: Compound,
    second_compound: Compound,
) -> dict:
    """Sweep candidate pit laps and return the optimum."""
    candidates: list[dict] = []
    for pit_lap in range(8, total_laps - 5):
        stints = [
            StintPlan(starting_compound, pit_lap),
            StintPlan(second_compound, total_laps - pit_lap),
        ]
        res = simulate_strategy(base_pace=base_pace, total_laps=total_laps, stints=stints)
        candidates.append({"pit_lap": pit_lap, "total_time": res["total_time_seconds"]})
    candidates.sort(key=lambda c: c["total_time"])
    best = candidates[0]
    return {
        "best_pit_lap": best["pit_lap"],
        "best_total_time": best["total_time"],
        "window": candidates[:6],
    }


# ── Qualifying micro-model ────────────────────────────────────────────────────
def predict_qualifying_top5(samples: list[dict]) -> list[dict]:
    """
    samples = [{
        driver_number, name, team_colour, fp1_best, fp2_best, fp3_best, fuel_kg,
        long_run_avg
    }, ...]

    We weight FP3 most heavily (most representative), subtract estimated fuel-effect
    on FP runs, and break ties using long-run averages.
    """
    if not samples:
        return []
    df = pd.DataFrame(samples)
    df = df.fillna(method="ffill").fillna(0)

    fuel_effect = df["fuel_kg"].fillna(0) * 0.035  # seconds added per kg
    # Normalize practice times into a single 'q_score' using fuel-corrected FP best.
    fp1 = df["fp1_best"] - fuel_effect * 0.5
    fp2 = df["fp2_best"] - fuel_effect * 0.75
    fp3 = df["fp3_best"] - fuel_effect  # FP3 typically lowest fuel
    q_score = 0.20 * fp1 + 0.30 * fp2 + 0.50 * fp3 + 0.05 * df.get("long_run_avg", 0)
    df["q_score"] = q_score
    df = df.sort_values("q_score").head(5).reset_index(drop=True)
    return [{
        "position": i + 1,
        "driver_number": int(row["driver_number"]),
        "name": row.get("name"),
        "team_colour": row.get("team_colour"),
        "predicted_time": round(float(row["q_score"]), 3),
    } for i, row in df.iterrows()]
