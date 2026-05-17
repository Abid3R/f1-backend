from fastapi import APIRouter
from services.jolpica_client import get_driver_standings

router = APIRouter()


@router.get("/drivers")
def driver_standings():
    return get_driver_standings()