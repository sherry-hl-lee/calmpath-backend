import pytest
from fastapi.testclient import TestClient

from app.api.routes import routes as route_routes
from app.main import app
from app.schemas.route import SensoryIndicator
from app.services.fake_services import (
    FakeRoutingProvider,
    FakeSensoryDataSource,
    FakeTransportService,
)
from app.services.route_geometry import Coordinate
from app.services.route_service_factory import create_route_service
from app.services.routing_provider import OpenRouteServiceProvider
from app.services.sensory_service import RdsSensoryDataSource
from app.services.transport_service import TransportService


@pytest.mark.asyncio
async def test_fake_mode_returns_all_demo_indicators_without_external_services(
    monkeypatch,
) -> None:
    def fail_if_mysql_is_created():
        raise AssertionError("fake mode must not create MySQLClient")

    monkeypatch.setattr(
        "app.services.sensory_service.MySQLClient",
        fail_if_mysql_is_created,
    )
    service = create_route_service("fake")

    response = await service.find_routes(
        Coordinate(-37.8183, 144.9671),
        Coordinate(-37.8102, 144.9628),
    )

    assert len(response.routes) == 3
    assert {route.sensory_indicator for route in response.routes} == {
        SensoryIndicator.HIGH,
        SensoryIndicator.LOW,
        SensoryIndicator.LIMITED_DATA,
    }
    assert all(route.geometry["type"] == "LineString" for route in response.routes)
    assert all(len(route.nearby_transport) == 2 for route in response.routes)
    assert {
        point.type
        for route in response.routes
        for point in route.nearby_transport
    } == {"tram", "train"}


def test_fake_mode_builds_only_fake_route_dependencies() -> None:
    service = create_route_service("fake")

    assert isinstance(service._routing_provider, FakeRoutingProvider)
    assert isinstance(service._sensory_service._data_source, FakeSensoryDataSource)
    assert isinstance(service._transport_service, FakeTransportService)


def test_rds_mode_builds_only_real_route_dependencies() -> None:
    service = create_route_service("rds")

    assert isinstance(service._routing_provider, OpenRouteServiceProvider)
    assert isinstance(service._sensory_service._data_source, RdsSensoryDataSource)
    assert isinstance(service._transport_service, TransportService)


def test_unknown_data_source_is_rejected() -> None:
    with pytest.raises(ValueError, match="DATA_SOURCE"):
        create_route_service("unexpected")


def test_fake_mode_works_through_public_route_endpoint(monkeypatch) -> None:
    monkeypatch.setattr(route_routes, "route_service", create_route_service("fake"))
    response = TestClient(app).get(
        "/api/v1/routes",
        params={
            "origin_latitude": -37.8183,
            "origin_longitude": 144.9671,
            "destination_latitude": -37.8102,
            "destination_longitude": 144.9628,
        },
    )

    assert response.status_code == 200
    assert len(response.json()["routes"]) == 3
