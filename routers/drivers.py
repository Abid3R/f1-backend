from fastapi import APIRouter
from services.jolpica_client import get_current_drivers

router = APIRouter()


@router.get("/current")
def current_drivers():
    return get_current_drivers()