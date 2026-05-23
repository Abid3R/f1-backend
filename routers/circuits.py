"""
/api/circuits/* — circuit dictionary + weather forecast.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from services.circuit_data import get_circuit, list_circuits
from services.weather_client import get_3day_forecast

router = APIRouter()


@router.get("/")
def all_circuits():
    """Return the full circuit catalogue."""
    return list_circuits()


@router.get("/{slug}")
def circuit_detail(slug: str):
    c = get_circuit(slug)
    if not c:
        raise HTTPException(status_code=404, detail=f"Unknown circuit '{slug}'.")
    return c


@router.get("/{slug}/weather")
def circuit_weather(slug: str):
    c = get_circuit(slug)
    if not c:
        raise HTTPException(status_code=404, detail=f"Unknown circuit '{slug}'.")
    forecast = get_3day_forecast(c["lat"], c["lon"])
    return {"circuit": {"slug": c["slug"], "name": c["name"]}, "forecast": forecast}
