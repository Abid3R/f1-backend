from fastapi import APIRouter
from services.openf1_client import get_race_schedule

router = APIRouter()


@router.get("/schedule")
def race_schedule(year: int = 2026):
    return get_race_schedule(year)