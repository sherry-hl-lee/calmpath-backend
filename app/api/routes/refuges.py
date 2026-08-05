from fastapi import APIRouter, Query

from app.schemas.refuge import Refuge
from app.services.refuge_service import RefugeService


router = APIRouter(prefix="/api/v1/refuges", tags=["refuges"])
refuge_service = RefugeService()


@router.get("/nearby", response_model=list[Refuge])
def get_nearby_refuges(
    latitude: float = Query(..., ge=-90, le=90),
    longitude: float = Query(..., ge=-180, le=180),
    radius_m: int = Query(..., gt=0),
) -> list[Refuge]:
    return refuge_service.find_nearby(latitude, longitude, radius_m)
