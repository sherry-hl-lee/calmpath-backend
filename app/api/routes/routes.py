import math
import zipfile

import httpx
from fastapi import APIRouter, HTTPException, Query

from app.schemas.route import RouteResponse
from app.services.route_geometry import Coordinate
from app.services.route_service_factory import create_route_service
from app.services.routing_provider import RoutingProviderError
from app.services.sensory_service import SensoryDataError


router = APIRouter(prefix="/api/v1/routes", tags=["routes"])
route_service = create_route_service()

CBD_MIN_LATITUDE = -37.8255
CBD_MAX_LATITUDE = -37.7990
CBD_MIN_LONGITUDE = 144.9460
CBD_MAX_LONGITUDE = 144.9900


@router.get("", response_model=RouteResponse)
async def get_routes(
    origin_latitude: float = Query(..., ge=-90, le=90),
    origin_longitude: float = Query(..., ge=-180, le=180),
    destination_latitude: float = Query(..., ge=-90, le=90),
    destination_longitude: float = Query(..., ge=-180, le=180),
) -> RouteResponse:
    coordinates = (
        origin_latitude,
        origin_longitude,
        destination_latitude,
        destination_longitude,
    )
    if not all(math.isfinite(value) for value in coordinates):
        raise HTTPException(status_code=422, detail="coordinates must be finite numbers")
    if origin_latitude == destination_latitude and origin_longitude == destination_longitude:
        raise HTTPException(status_code=422, detail="origin and destination must be different")
    if not (
        CBD_MIN_LATITUDE <= destination_latitude <= CBD_MAX_LATITUDE
        and CBD_MIN_LONGITUDE <= destination_longitude <= CBD_MAX_LONGITUDE
    ):
        raise HTTPException(
            status_code=422,
            detail="destination must be inside Melbourne CBD",
        )

    try:
        return await route_service.find_routes(
            Coordinate(origin_latitude, origin_longitude),
            Coordinate(destination_latitude, destination_longitude),
        )
    except RoutingProviderError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except SensoryDataError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except (httpx.HTTPError, zipfile.BadZipFile) as error:
        raise HTTPException(
            status_code=502,
            detail="An upstream route or open-data service is unavailable",
        ) from error
