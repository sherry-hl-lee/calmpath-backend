import pytest
from fastapi.testclient import TestClient

from app.api.routes import routes as route_routes
from app.core.config import ORS_BASE_URL
from app.main import app
from app.schemas.route import (
    RouteOption,
    RouteResponse,
    SensoryIndicator,
    TransitAccessPoint,
)


client = TestClient(app)


def test_default_ors_endpoint_uses_current_heigit_host():
    assert ORS_BASE_URL == (
        "https://api.heigit.org/openrouteservice/v2/directions/foot-walking/geojson"
    )


class FakeRouteService:
    async def find_routes(self, origin, destination) -> RouteResponse:
        return RouteResponse(
            routes=[
                RouteOption(
                    id="route-1",
                    distance_m=900,
                    duration_s=700,
                    sensory_indicator=SensoryIndicator.LOW,
                    sensory_score=350,
                    sensor_coverage=0.6,
                    sensors_used=3,
                    nearby_transport=[
                        TransitAccessPoint(
                            id="station-1",
                            name="Melbourne Central",
                            type="train",
                            latitude=-37.8102,
                            longitude=144.9628,
                            distance_to_route_m=50,
                        )
                    ],
                    geometry={
                        "type": "LineString",
                        "coordinates": [
                            [origin.longitude, origin.latitude],
                            [destination.longitude, destination.latitude],
                        ],
                    },
                ),
                RouteOption(
                    id="route-2",
                    distance_m=1100,
                    duration_s=820,
                    sensory_indicator=SensoryIndicator.LIMITED_DATA,
                    sensory_score=None,
                    sensor_coverage=0.1,
                    sensors_used=0,
                    nearby_transport=[],
                    geometry={
                        "type": "LineString",
                        "coordinates": [
                            [origin.longitude, origin.latitude],
                            [destination.longitude, destination.latitude],
                        ],
                    },
                ),
            ]
        )


@pytest.fixture(autouse=True)
def install_fake_route_service(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(route_routes, "route_service", FakeRouteService())


def valid_params() -> dict[str, float]:
    return {
        "origin_latitude": -37.8183,
        "origin_longitude": 144.9671,
        "destination_latitude": -37.8102,
        "destination_longitude": 144.9628,
    }


def test_routes_meet_us11_response_contract() -> None:
    response = client.get("/api/v1/routes", params=valid_params())

    assert response.status_code == 200
    routes = response.json()["routes"]
    assert len(routes) == 2
    assert routes[0]["sensory_indicator"] == "Low"
    assert routes[1]["sensory_indicator"] == "Limited Data"
    assert routes[0]["nearby_transport"][0]["type"] == "train"
    assert routes[0]["geometry"]["type"] == "LineString"


def test_destination_outside_melbourne_cbd_returns_422() -> None:
    params = valid_params()
    params["destination_latitude"] = -37.9

    response = client.get("/api/v1/routes", params=params)

    assert response.status_code == 422
    assert response.json()["detail"] == "destination must be inside Melbourne CBD"


def test_origin_and_destination_must_differ() -> None:
    params = valid_params()
    params["destination_latitude"] = params["origin_latitude"]
    params["destination_longitude"] = params["origin_longitude"]

    response = client.get("/api/v1/routes", params=params)

    assert response.status_code == 422


def test_cors_allows_netlify_frontend_to_call_routes() -> None:
    response = client.get(
        "/api/v1/routes",
        params=valid_params(),
        headers={"Origin": "https://calmpath-tp10.netlify.app"},
    )

    assert response.status_code == 200
    assert (
        response.headers["access-control-allow-origin"]
        == "https://calmpath-tp10.netlify.app"
    )
