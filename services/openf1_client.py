import requests
from fastapi import HTTPException

BASE_URL = "https://api.openf1.org/v1"
JOLPICA_URL = "https://api.jolpi.ca/ergast/f1"


# ── Helper: convert GMT offset hours to "+HH:MM" string ──────────────────────
def _format_gmt_offset(hours_str: str) -> str:
    """Turn '15:00:00' + a date into nothing useful; Jolpica gives UTC times so
    we don't have an offset. Return empty string for missing data."""
    return ""


# ── Fallback: fetch schedule from Jolpica (Ergast format) ────────────────────
def _get_schedule_from_jolpica(year: int):
    url = f"{JOLPICA_URL}/{year}.json"

    response = requests.get(
        url,
        timeout=30,
        headers={"User-Agent": "f1-stats-backend-learning-project"},
    )
    response.raise_for_status()
    data = response.json()

    races = data["MRData"]["RaceTable"]["Races"]
    clean_data = []

    for race in races:
        circuit = race.get("Circuit", {})
        location = circuit.get("Location", {})

        # Combine date + time into an ISO-style timestamp matching OpenF1's shape
        date = race.get("date", "")
        time = race.get("time", "")
        date_start = f"{date}T{time}" if date and time else date or None

        clean_data.append({
            "meeting_key": int(race.get("round", 0)) if race.get("round") else None,
            "meeting_name": race.get("raceName"),
            "country_name": location.get("country"),
            "location": location.get("locality"),
            "date_start": date_start,
            "date_end": None,
            "gmt_offset": "",
        })

    return clean_data


# ── Main: OpenF1 first, Jolpica fallback ─────────────────────────────────────
def get_race_schedule(year: int = 2026):
    url = f"{BASE_URL}/meetings?year={year}"

    # Attempt 1: OpenF1
    try:
        response = requests.get(
            url,
            timeout=15,
            headers={"User-Agent": "f1-stats-backend-learning-project"},
        )
        response.raise_for_status()
        data = response.json()

        if data:  # OpenF1 sometimes returns [] for future seasons
            clean_data = []
            for race in data:
                clean_data.append({
                    "meeting_key": race.get("meeting_key"),
                    "meeting_name": race.get("meeting_name"),
                    "country_name": race.get("country_name"),
                    "location": race.get("location"),
                    "date_start": race.get("date_start"),
                    "date_end": race.get("date_end"),
                    "gmt_offset": race.get("gmt_offset"),
                })
            return clean_data

        # Empty response → fall through to Jolpica
        print(f"[schedule] OpenF1 returned empty for {year}, falling back to Jolpica")

    except requests.exceptions.RequestException as error:
        print(f"[schedule] OpenF1 failed ({error}), falling back to Jolpica")

    # Attempt 2: Jolpica fallback
    try:
        return _get_schedule_from_jolpica(year)

    except requests.exceptions.Timeout:
        raise HTTPException(
            status_code=504,
            detail="Both OpenF1 and Jolpica APIs timed out. Please try again.",
        )
    except requests.exceptions.RequestException as error:
        raise HTTPException(
            status_code=503,
            detail=f"Both OpenF1 and Jolpica failed. Last error: {str(error)}",
        )
