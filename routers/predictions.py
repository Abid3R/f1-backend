from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


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


@router.post("/pitstop-demo")
def predict_pitstop_demo(data: PitStopInput):
    probability = 0.10
    reasons = []

    compound = data.compound.upper()

    if compound == "SOFT":
        probability += 0.20
        reasons.append("Soft tyres usually degrade faster.")
    elif compound == "MEDIUM":
        probability += 0.12
        reasons.append("Medium tyres have moderate degradation.")
    elif compound == "HARD":
        probability += 0.06
        reasons.append("Hard tyres usually last longer.")
    elif compound in ["INTERMEDIATE", "WET"]:
        probability += 0.18
        reasons.append("Wet-weather tyres may require strategy changes.")

    if data.tyre_life >= 20:
        probability += 0.30
        reasons.append("Tyre life is high, so pit stop chance increases.")
    elif data.tyre_life >= 12:
        probability += 0.18
        reasons.append("Tyres have completed a medium-length stint.")
    else:
        reasons.append("Tyres are still relatively fresh.")

    if data.lap_time_delta >= 1.5:
        probability += 0.22
        reasons.append("Lap time is getting much slower.")
    elif data.lap_time_delta >= 0.7:
        probability += 0.12
        reasons.append("Lap time degradation is visible.")

    if data.cumulative_degradation >= 4:
        probability += 0.20
        reasons.append("Cumulative tyre degradation is high.")
    elif data.cumulative_degradation >= 2:
        probability += 0.10
        reasons.append("Cumulative degradation is moderate.")

    if data.race_progress > 0.30 and data.race_progress < 0.85:
        probability += 0.08
        reasons.append("Race is in a normal pit-window phase.")

    if data.position_change < 0:
        probability += 0.07
        reasons.append("Driver is losing position, so a pit stop may help.")

    if data.position <= 5 and data.lap_time_delta > 0.7:
        probability += 0.05
        reasons.append("Front runners often pit to protect track position.")

    probability = min(probability, 0.95)

    will_pit = probability >= 0.50

    if not reasons:
        reasons.append("No strong pit stop signal found.")

    return {
        "driver": data.driver,
        "race": data.race,
        "will_pit": will_pit,
        "probability": round(probability, 3),
        "percentage": round(probability * 100, 1),
        "compound": compound,
        "reason": reasons
    }