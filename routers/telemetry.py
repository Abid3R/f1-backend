"""
/api/telemetry/* — telemetry overlay, intervals (live gap), positions (live map),
and tyre stint history.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from services.telemetry_client import (
    get_live_intervals,
    get_live_positions,
    get_stints,
    get_telemetry_for_lap,
)

router = APIRouter()


@router.get("/compare")
def compare_telemetry(
    year: int = Query(..., ge=2018, le=2030),
    meeting_key: Optional[int] = Query(None),
    session_name: str = Query("Race"),
    driver_a: int = Query(..., description="Driver #1 car number"),
    driver_b: int = Query(..., description="Driver #2 car number"),
    lap_a: int = Query(..., ge=1, le=200),
    lap_b: Optional[int] = Query(None, ge=1, le=200),
):
    """
    Return a side-by-side telemetry trace for two drivers on the same lap
    (or different laps, if `lap_b` is provided).

    Used by /telemetry on the frontend.
    """
    if driver_a == driver_b and lap_b is None:
        raise HTTPException(status_code=400, detail="Pick two different drivers or two different laps.")

    a = get_telemetry_for_lap(year, meeting_key, session_name, driver_a, lap_a)
    b = get_telemetry_for_lap(year, meeting_key, session_name, driver_b, lap_b or lap_a)
    return {"driver_a": a, "driver_b": b}


@router.get("/intervals")
def latest_intervals(session_key: Optional[int] = Query(None)):
    """Latest gap-to-leader / interval for every driver in the current race."""
    return get_live_intervals(session_key)


@router.get("/positions")
def latest_positions(session_key: Optional[int] = Query(None)):
    """Latest (x,y) coordinates for every driver — feeds the SVG track map."""
    return get_live_positions(session_key)


@router.get("/stints")
def stint_history(
    session_key: Optional[int] = Query(None),
    driver_number: Optional[int] = Query(None),
):
    """Full tyre stint timeline. Optionally filter to a single driver."""
    return get_stints(session_key, driver_number)
