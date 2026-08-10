import logging

from app.core.config import DATA_SOURCE
from app.services.fake_services import (
    FakeRouteScenario,
    FakeRoutingProvider,
    FakeSensoryDataSource,
    FakeTransportService,
)
from app.services.route_service import RouteService
from app.services.sensory_service import SensoryService


logger = logging.getLogger(__name__)


def create_route_service(data_source: str | None = None) -> RouteService:
    selected = (data_source or DATA_SOURCE).strip().lower()
    if selected == "fake":
        logger.warning("US1.1 is running with fake local development data")
        scenario = FakeRouteScenario()
        return RouteService(
            routing_provider=FakeRoutingProvider(scenario),
            sensory_service=SensoryService(FakeSensoryDataSource(scenario)),
            transport_service=FakeTransportService(),
        )
    if selected == "rds":
        return RouteService()
    raise ValueError("DATA_SOURCE must be either 'fake' or 'rds'")
