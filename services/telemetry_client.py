"""
OpenF1 telemetry helpers used by the /api/telemetry/* routes.

OpenF1 exposes raw car_data (speed/rpm/gear/throttle/brake/drs) and location
samples keyed by session_key + driver_number.  We resolve the latest race
session for a given year+meeting, then pull a single lap of samples for two
drivers so the frontend can render an overlaid telemetry trace.
"""
from __future__ import annotations

import requests
from fastapi import HTTPException

OPENF1 = "https://api.openf1.org/v1"
_HEADERS = {"User-Agent": "f1-stats-backend-telemetry"}
_TIMEOUT = 15


def _get(path: str, **params) -> list[dict]:
    """Thin wrapper around `requests.get` that always returns a list."""
    try:
        r = requests.get(f"{OPENF1}/{path}", params=params, headers=_HEADERS, timeout=_TIMEOUT)
        r.raise_for_status()
        data = r.json()
        return data if isinstance(data, list) else []
    except requests.exceptions.RequestException as err:
        raise HTTPException(status_code=503, detail=f"OpenF1 unreachable: {err}") from err


def _resolve_session_key(year: int, meeting_key: int | None, session_name: str = "Race") -> int:
    """Find the session_key for the given meeting + session type."""
    params = {"year": year, "session_name": session_name}
    if meeting_key is not None:
        params["meeting_key"] = meeting_key
    sessions = _get("sessions", **params)
    if not sessions:
        raise HTTPException(status_code=404, detail="No matching OpenF1 session was found.")
    # newest first
    sessions.sort(key=lambda s: s.get("date_start") or "", reverse=True)
    return int(sessions[0]["session_key"])


def get_telemetry_for_lap(
    year: int,
    meeting_key: int | None,
    session_name: str,
    driver_number: int,
    lap_number: int,
) -> dict:
    """
    Pull a single lap of car_data samples for a driver.

    Returns:
        {
            "driver_number": 1,
            "lap_number": 32,
            "samples": [{ "t": iso, "speed": .., "rpm": .., "gear": .., "throttle": .., "brake": .., "drs": .. }, ...]
        }
    """
    session_key = _resolve_session_key(year, meeting_key, session_name)

    laps = _get("laps", session_key=session_key, driver_number=driver_number, lap_number=lap_number)
    if not laps:
        raise HTTPException(status_code=404, detail=f"Lap {lap_number} not found for driver #{driver_number}.")
    lap = laps[0]
    start = lap.get("date_start")
    if not start:
        raise HTTPException(status_code=500, detail="Lap is missing a start timestamp.")

    # Pull car_data samples bounded by lap start + an upper end (next lap start or +120s safety).
    # OpenF1's date filters use 'date>=...' / 'date<...' query syntax.
    samples = _get(
        "car_data",
        session_key=session_key,
        driver_number=driver_number,
        **{"date>": start},
    )

    # Filter down to ~75s window – more than any F1 lap.
    from datetime import datetime, timedelta, timezone

    def _parse(ts: str) -> datetime:
        return datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(timezone.utc)

    start_dt = _parse(start)
    cutoff = start_dt + timedelta(seconds=120)
    cleaned = []
    for s in samples:
        d = s.get("date")
        if not d:
            continue
        try:
            dt = _parse(d)
        except ValueError:
            continue
        if dt < start_dt or dt > cutoff:
            continue
        cleaned.append({
            "t": d,
            "elapsed": round((dt - start_dt).total_seconds(), 3),
            "speed": s.get("speed"),
            "rpm": s.get("rpm"),
            "gear": s.get("n_gear"),
            "throttle": s.get("throttle"),
            "brake": s.get("brake"),
            "drs": s.get("drs"),
        })

    if not cleaned:
        raise HTTPException(status_code=404, detail="No telemetry samples returned for this lap.")

    return {
        "driver_number": driver_number,
        "lap_number": lap_number,
        "lap_duration": lap.get("lap_duration"),
        "samples": cleaned,
    }


def get_live_intervals(session_key: int | None = None) -> list[dict]:
    """Latest intervals for each driver in the most recent race session."""
    if session_key is None:
        sessions = _get("sessions", session_name="Race")
        if not sessions:
            raise HTTPException(status_code=404, detail="No race sessions available.")
        sessions.sort(key=lambda s: s.get("date_start") or "", reverse=True)
        session_key = int(sessions[0]["session_key"])

    intervals = _get("intervals", session_key=session_key)
    # Reduce to most-recent record per driver_number
    latest: dict[int, dict] = {}
    for row in intervals:
        dn = row.get("driver_number")
        if dn is None:
            continue
        prev = latest.get(dn)
        if not prev or (row.get("date") or "") > (prev.get("date") or ""):
            latest[dn] = row
    result = []
    for dn, row in latest.items():
        result.append({
            "driver_number": dn,
            "gap_to_leader": row.get("gap_to_leader"),
            "interval": row.get("interval"),
            "date": row.get("date"),
        })
    result.sort(key=lambda x: (x["gap_to_leader"] if isinstance(x["gap_to_leader"], (int, float)) else 99999))
    return result


def get_live_positions(session_key: int | None = None) -> list[dict]:
    """Latest (x,y) location of each driver for the SVG track map."""
    if session_key is None:
        sessions = _get("sessions", session_name="Race")
        if not sessions:
            raise HTTPException(status_code=404, detail="No race sessions available.")
        sessions.sort(key=lambda s: s.get("date_start") or "", reverse=True)
        session_key = int(sessions[0]["session_key"])

    loc = _get("location", session_key=session_key)
    drivers = _get("drivers", session_key=session_key)
    driver_meta = {int(d["driver_number"]): d for d in drivers if d.get("driver_number") is not None}

    latest: dict[int, dict] = {}
    for row in loc:
        dn = row.get("driver_number")
        if dn is None:
            continue
        prev = latest.get(dn)
        if not prev or (row.get("date") or "") > (prev.get("date") or ""):
            latest[dn] = row

    result = []
    for dn, row in latest.items():
        meta = driver_meta.get(int(dn), {})
        result.append({
            "driver_number": int(dn),
            "x": row.get("x"),
            "y": row.get("y"),
            "z": row.get("z"),
            "date": row.get("date"),
            "name_acronym": meta.get("name_acronym"),
            "team_name": meta.get("team_name"),
            "team_colour": meta.get("team_colour"),
            "full_name": meta.get("full_name"),
        })
    return result


def get_stints(session_key: int | None = None, driver_number: int | None = None) -> list[dict]:
    """Tyre stint history for the latest race (optionally filtered to a driver)."""
    if session_key is None:
        sessions = _get("sessions", session_name="Race")
        if not sessions:
            raise HTTPException(status_code=404, detail="No race sessions available.")
        sessions.sort(key=lambda s: s.get("date_start") or "", reverse=True)
        session_key = int(sessions[0]["session_key"])

    params = {"session_key": session_key}
    if driver_number is not None:
        params["driver_number"] = driver_number

    stints = _get("stints", **params)
    return [{
        "driver_number": s.get("driver_number"),
        "stint_number": s.get("stint_number"),
        "compound": s.get("compound"),
        "tyre_age_at_start": s.get("tyre_age_at_start"),
        "lap_start": s.get("lap_start"),
        "lap_end": s.get("lap_end"),
    } for s in stints]
