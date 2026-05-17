import requests
from fastapi import HTTPException

BASE_URL = "https://api.jolpi.ca/ergast/f1"


def clean_driver_standings(data):
    standings_lists = data["MRData"]["StandingsTable"]["StandingsLists"]

    if not standings_lists:
        return []

    driver_standings = standings_lists[0]["DriverStandings"]

    clean_data = []

    for item in driver_standings:
        driver = item["Driver"]
        constructor = item["Constructors"][0]

        clean_data.append({
            "position": item["position"],
            "driver": driver["givenName"] + " " + driver["familyName"],
            "code": driver.get("code", ""),
            "team": constructor["name"],
            "points": item["points"],
            "wins": item["wins"]
        })

    return clean_data


def get_driver_standings():
    url = f"{BASE_URL}/current/driverStandings.json"

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

        return clean_driver_standings(data)

    except requests.exceptions.Timeout:
        raise HTTPException(
            status_code=504,
            detail="Jolpica F1 API took too long to respond. Please try again."
        )

    except requests.exceptions.RequestException as error:
        raise HTTPException(
            status_code=503,
            detail=f"Could not connect to Jolpica F1 API. Error: {str(error)}"
        )


def get_current_drivers():
    url = f"{BASE_URL}/current/driverStandings.json"

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

        standings_lists = data["MRData"]["StandingsTable"]["StandingsLists"]

        if not standings_lists:
            return []

        driver_standings = standings_lists[0]["DriverStandings"]

        drivers = []

        for item in driver_standings:
            driver = item["Driver"]
            constructor = item["Constructors"][0]

            drivers.append({
                "driver_id": driver.get("driverId"),
                "permanent_number": driver.get("permanentNumber", ""),
                "code": driver.get("code", ""),
                "given_name": driver.get("givenName", ""),
                "family_name": driver.get("familyName", ""),
                "full_name": driver.get("givenName", "") + " " + driver.get("familyName", ""),
                "nationality": driver.get("nationality", ""),
                "team": constructor.get("name", ""),
                "points": item.get("points", "0"),
                "wins": item.get("wins", "0"),
                "standing_position": item.get("position", "")
            })

        return drivers

    except requests.exceptions.Timeout:
        raise HTTPException(
            status_code=504,
            detail="Jolpica F1 API took too long to respond. Please try again."
        )

    except requests.exceptions.RequestException as error:
        raise HTTPException(
            status_code=503,
            detail=f"Could not connect to Jolpica F1 API. Error: {str(error)}"
        )