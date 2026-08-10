import io
import zipfile

import httpx
import pytest

from app.services.route_geometry import Coordinate
from app.services.transport_service import TransportService


def build_inner_feed(rows: str) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("stops.txt", rows)
    return buffer.getvalue()


def build_victorian_gtfs() -> bytes:
    train_rows = (
        "stop_id,stop_name,stop_lat,stop_lon,location_type,parent_station\n"
        "station-1,Melbourne Central,-37.8102,144.9628,1,\n"
        "platform-1,Melbourne Central Platform 1,-37.8101,144.9628,0,station-1\n"
    )
    tram_rows = (
        "stop_id,stop_name,stop_lat,stop_lon,location_type,parent_station\n"
        "tram-1,Swanston Street Stop,-37.8103,144.9630,0,\n"
    )
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("2/google_transit.zip", build_inner_feed(train_rows))
        archive.writestr("3/google_transit.zip", build_inner_feed(tram_rows))
    return buffer.getvalue()


@pytest.mark.asyncio
async def test_nested_victorian_gtfs_returns_train_stations_and_tram_stops() -> None:
    gtfs_bytes = build_victorian_gtfs()

    async def respond(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=gtfs_bytes, request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        access_points = await TransportService().nearby(
            client,
            [Coordinate(-37.8102, 144.9628)],
        )

    assert {(point.id, point.type) for point in access_points} == {
        ("station-1", "train"),
        ("tram-1", "tram"),
    }
    assert all(point.id != "platform-1" for point in access_points)
