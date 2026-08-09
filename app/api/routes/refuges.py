import math

from fastapi import APIRouter, HTTPException, Query

from app.core.database import MySQLClient
from app.schemas.refuge import NearbyRefuge, RefugeAddress
from app.services.address_service import AddressService
from app.services.refuge_service import RefugeService


router = APIRouter(prefix="/api/v1/refuges", tags=["refuges"])
database_client = MySQLClient()
refuge_service = RefugeService(database_client)
address_service = AddressService(database_client)


@router.get("/nearby", response_model=list[NearbyRefuge])
def get_nearby_refuges(
    latitude: float = Query(..., ge=-90, le=90),
    longitude: float = Query(..., ge=-180, le=180),
    radius_m: float = Query(..., gt=0),
) -> list[NearbyRefuge]:
    return refuge_service.find_nearby(latitude, longitude, radius_m)


@router.get("/address", response_model=RefugeAddress)
def get_refuge_address(
    latitude: float = Query(..., ge=-90, le=90),
    longitude: float = Query(..., ge=-180, le=180),
) -> RefugeAddress:
    if not math.isfinite(latitude) or not math.isfinite(longitude):
        raise HTTPException(
            status_code=422,
            detail="latitude and longitude must be finite numbers",
        )

    result = address_service.find_address(latitude, longitude)
    if result is None:
        raise HTTPException(
            status_code=404,
            detail="No matched address found for the selected refuge",
        )

    return result
