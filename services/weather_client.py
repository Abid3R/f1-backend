"""
Free-tier weather forecast for circuit locations using Open-Meteo
(https://open-meteo.com).  No API key required.

We expose a small 3-day forecast (air temp, precipitation, wind) keyed by
latitude/longitude.  Race-day forecast for a circuit is the consumer.
"""
from __future__ import annotations

import requests
from fastapi import HTTPException

BASE = "https://api.open-meteo.com/v1/forecast"
_HEADERS = {"User-Agent": "f1-stats-backend-weather"}


def get_3day_forecast(lat: float, lon: float) -> dict:
    """Returns a compact 3-day daily forecast at the supplied location."""
    params = {
        "latitude": lat,
        "longitude": lon,
        "daily": ",".join([
            "temperature_2m_max",
            "temperature_2m_min",
            "precipitation_sum",
            "precipitation_probability_max",
            "wind_speed_10m_max",
            "weather_code",
        ]),
        "current": ",".join(["temperature_2m", "precipitation", "wind_speed_10m", "weather_code"]),
        "forecast_days": 3,
        "timezone": "auto",
    }
    try:
        r = requests.get(BASE, params=params, timeout=12, headers=_HEADERS)
        r.raise_for_status()
        data = r.json()
    except requests.exceptions.RequestException as err:
        raise HTTPException(status_code=503, detail=f"Weather service unavailable: {err}") from err

    daily = data.get("daily") or {}
    days: list[dict] = []
    times = daily.get("time") or []
    for i, day in enumerate(times):
        days.append({
            "date": day,
            "t_max": _safe(daily.get("temperature_2m_max"), i),
            "t_min": _safe(daily.get("temperature_2m_min"), i),
            "precipitation_sum": _safe(daily.get("precipitation_sum"), i),
            "rain_probability": _safe(daily.get("precipitation_probability_max"), i),
            "wind_speed_max": _safe(daily.get("wind_speed_10m_max"), i),
            "weather_code": _safe(daily.get("weather_code"), i),
        })

    current = data.get("current") or {}
    return {
        "latitude": data.get("latitude"),
        "longitude": data.get("longitude"),
        "timezone": data.get("timezone"),
        "current": {
            "temperature": current.get("temperature_2m"),
            "precipitation": current.get("precipitation"),
            "wind_speed": current.get("wind_speed_10m"),
            "weather_code": current.get("weather_code"),
        },
        "days": days,
    }


def _safe(arr, i):
    if not isinstance(arr, list):
        return None
    if i < 0 or i >= len(arr):
        return None
    return arr[i]
