import math
from contextvars import ContextVar

import httpx

from app.core.config import HIGH_SENSORY_THRESHOLD, ROUTE_SAMPLE_INTERVAL_M
from app.schemas.route import TransitAccessPoint
from app.services.route_geometry import Coordinate, haversine_m, sample_route
from app.services.routing_provider import GeneratedRoute
from app.services.sensory_service import PedestrianSensor


class FakeRouteScenario:
    """Request-scoped-style state shared by deterministic local fake providers."""

    def __init__(self) -> None:
        self._sensors: ContextVar[tuple[PedestrianSensor, ...]] = ContextVar(
            f"fake_sensors_{id(self)}",
            default=(),
        )
        self._counts: ContextVar[dict[str, float]] = ContextVar(
            f"fake_counts_{id(self)}",
            default={},
        )

    @property
    def sensors(self) -> tuple[PedestrianSensor, ...]:
        return self._sensors.get()

    def count_for(self, sensor_id: str) -> float | None:
        return self._counts.get().get(sensor_id)

    def prepare_sensors(self, routes: list[GeneratedRoute]) -> None:
        sensors: list[PedestrianSensor] = []
        counts: dict[str, float] = {}
        route_counts = (
            (routes[0], HIGH_SENSORY_THRESHOLD + 200),
            (routes[1], max(0.0, HIGH_SENSORY_THRESHOLD / 2)),
        )
        for route, count in route_counts:
            samples = sample_route(route.coordinates, ROUTE_SAMPLE_INTERVAL_M)
            start = max(1, math.floor(len(samples) * 0.25))
            end = max(start + 1, math.ceil(len(samples) * 0.75))
            for index, coordinate in enumerate(samples[start:end]):
                sensor_id = f"{route.id}-sensor-{index + 1}"
                sensors.append(PedestrianSensor(sensor_id, coordinate))
                counts[sensor_id] = count
        self._sensors.set(tuple(sensors))
        self._counts.set(counts)


class FakeRoutingProvider:
    """Generate three deterministic alternatives without calling ORS."""

    def __init__(self, scenario: FakeRouteScenario) -> None:
        self._scenario = scenario

    @staticmethod
    def _build_route(
        route_id: str,
        coordinates: list[Coordinate],
    ) -> GeneratedRoute:
        distance_m = sum(
            haversine_m(start, end)
            for start, end in zip(coordinates, coordinates[1:])
        )
        return GeneratedRoute(
            id=route_id,
            distance_m=round(distance_m, 1),
            duration_s=round(distance_m / 1.3, 1),
            coordinates=coordinates,
        )

    async def generate(
        self,
        client: httpx.AsyncClient,
        origin: Coordinate,
        destination: Coordinate,
    ) -> list[GeneratedRoute]:
        latitude_delta = destination.latitude - origin.latitude
        longitude_delta = destination.longitude - origin.longitude
        vector_length = math.hypot(latitude_delta, longitude_delta) or 1.0
        offset = 0.004
        perpendicular_latitude = -longitude_delta / vector_length * offset
        perpendicular_longitude = latitude_delta / vector_length * offset
        midpoint = Coordinate(
            latitude=(origin.latitude + destination.latitude) / 2,
            longitude=(origin.longitude + destination.longitude) / 2,
        )
        high_midpoint = Coordinate(
            midpoint.latitude + perpendicular_latitude,
            midpoint.longitude + perpendicular_longitude,
        )
        low_midpoint = Coordinate(
            midpoint.latitude - perpendicular_latitude,
            midpoint.longitude - perpendicular_longitude,
        )

        routes = [
            self._build_route(
                "fake-route-high",
                [origin, high_midpoint, destination],
            ),
            self._build_route(
                "fake-route-low",
                [origin, low_midpoint, destination],
            ),
            self._build_route(
                "fake-route-limited",
                [origin, midpoint, destination],
            ),
        ]
        self._scenario.prepare_sensors(routes)
        return routes


class FakeSensoryDataSource:
    """Supply deterministic in-memory sensors and counts for local development."""

    def __init__(self, scenario: FakeRouteScenario) -> None:
        self._scenario = scenario

    async def active_sensors(
        self,
        client: httpx.AsyncClient,
    ) -> list[PedestrianSensor]:
        return list(self._scenario.sensors)

    async def latest_count(
        self,
        client: httpx.AsyncClient,
        sensor_id: str,
    ) -> float | None:
        return self._scenario.count_for(sensor_id)


class FakeTransportService:
    """Return schema-compatible demo access points without downloading GTFS."""

    async def nearby(
        self,
        client: httpx.AsyncClient,
        route_samples: list[Coordinate],
    ) -> list[TransitAccessPoint]:
        if not route_samples:
            return []
        tram_coordinate = route_samples[len(route_samples) // 3]
        train_coordinate = route_samples[(2 * len(route_samples)) // 3]
        return [
            TransitAccessPoint(
                id="fake-tram-1",
                name="Demo Tram Stop",
                type="tram",
                latitude=tram_coordinate.latitude,
                longitude=tram_coordinate.longitude,
                distance_to_route_m=0,
            ),
            TransitAccessPoint(
                id="fake-train-1",
                name="Demo Train Station",
                type="train",
                latitude=train_coordinate.latitude,
                longitude=train_coordinate.longitude,
                distance_to_route_m=0,
            ),
        ]
