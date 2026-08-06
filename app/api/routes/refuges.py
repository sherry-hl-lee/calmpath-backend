import math

from fastapi import APIRouter, HTTPException, Query, Request

from app.schemas.refuge import NearbyRefuge, RefugeAddress
from app.services.address_service import (
    AddressRateLimitExceeded,
    AddressService,
    AddressUpstreamError,
)
from app.services.refuge_service import RefugeService


router = APIRouter(prefix="/api/v1/refuges", tags=["refuges"])
refuge_service = RefugeService()
address_service = AddressService()


@router.get("/nearby", response_model=list[NearbyRefuge])
def get_nearby_refuges(
    latitude: float = Query(..., ge=-90, le=90),
    longitude: float = Query(..., ge=-180, le=180),
    radius_m: float = Query(..., gt=0),
) -> list[NearbyRefuge]:
    return refuge_service.find_nearby(latitude, longitude, radius_m)


@router.get("/address", response_model=RefugeAddress)
def get_refuge_address(
    request: Request,
    latitude: float = Query(..., ge=-90, le=90),
    longitude: float = Query(..., ge=-180, le=180),
) -> RefugeAddress:
    if not math.isfinite(latitude) or not math.isfinite(longitude):
        raise HTTPException(
            status_code=422,
            detail="latitude and longitude must be finite numbers",
        )

    client_ip = request.client.host if request.client else "unknown"
    try:
        result = address_service.find_address(latitude, longitude, client_ip)
    except AddressRateLimitExceeded as error:
        raise HTTPException(
            status_code=429,
            detail="Address lookup rate limit exceeded",
            headers={"Retry-After": str(error.retry_after_seconds)},
        ) from error
    except AddressUpstreamError as error:
        headers = {}
        if error.retry_after:
            headers["Retry-After"] = error.retry_after
        raise HTTPException(
            status_code=503,
            detail=str(error),
            headers=headers or None,
        ) from error

    if result is None:
        raise HTTPException(
            status_code=404,
            detail="No valid street address found within 200 metres",
        )

    return result
