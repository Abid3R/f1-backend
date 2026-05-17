import requests
from fastapi import HTTPException

BASE_URL = "https://api.openf1.org/v1"


def get_race_schedule(year: int = 2026):
    url = f"{BASE_URL}/meetings?year={year}"

    try:
        response = requests.get(
            url,
            timeout=30,
            headers={
                "User-Agent": "f1-stats-backend-learning-project"
            }
        )

        response.raise_for_status()
        data = response.json()

        clean_data = []

        for race in data:
            clean_data.append({
                "meeting_key": race.get("meeting_key"),
                "meeting_name": race.get("meeting_name"),
                "country_name": race.get("country_name"),
                "location": race.get("location"),
                "date_start": race.get("date_start"),
                "date_end": race.get("date_end"),
                "gmt_offset": race.get("gmt_offset")
            })

        return clean_data

    except requests.exceptions.Timeout:
        raise HTTPException(
            status_code=504,
            detail="OpenF1 API took too long to respond. Please try again."
        )

    except requests.exceptions.RequestException as error:
        raise HTTPException(
            status_code=503,
            detail=f"Could not connect to OpenF1 API. Error: {str(error)}"
        )