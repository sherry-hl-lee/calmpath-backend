from typing import Protocol

import httpx

from app.core.config import ROUTE_SAMPLE_INTERVAL_M, UPSTREAM_TIMEOUT_SECONDS
from app.schemas.route import RouteOption, RouteResponse
from app.services.route_geometry import Coordinate, sample_route
from app.services.routing_provider import OpenRouteServiceProvider
from app.services.sensory_service import SensoryService
from app.services.transport_service import TransportService


class RoutingProvider(Protocol):
    async def generate(
        self,
        client: httpx.AsyncClient,
        origin: Coordinate,
        destination: Coordinate,
    ): ...


class RouteService:
    def __init__(
        self,
        routing_provider: RoutingProvider | None = None,
        sensory_service: SensoryService | None = None,
        transport_service: TransportService | None = None,
    ) -> None:
        self._routing_provider = routing_provider or OpenRouteServiceProvider()
        self._sensory_service = sensory_service or SensoryService()
        self._transport_service = transport_service or TransportService()

    async def find_routes(
        self,
        origin: Coordinate,
        destination: Coordinate,
    ) -> RouteResponse:
        async with httpx.AsyncClient(
            timeout=UPSTREAM_TIMEOUT_SECONDS,
            follow_redirects=True,
            trust_env=False,
        ) as client:
            generated_routes = await self._routing_provider.generate(
                client,
                origin,
                destination,
            )
            route_options: list[RouteOption] = []
            for generated_route in generated_routes:
                route_samples = sample_route(
                    generated_route.coordinates,
                    ROUTE_SAMPLE_INTERVAL_M,
                )
                sensory = await self._sensory_service.assess(client, route_samples)
                nearby_transport = await self._transport_service.nearby(
                    client,
                    route_samples,
                )
                route_options.append(
                    RouteOption(
                        id=generated_route.id,
                        distance_m=generated_route.distance_m,
                        duration_s=generated_route.duration_s,
                        sensory_indicator=sensory.indicator,
                        sensory_score=sensory.score,
                        sensor_coverage=round(sensory.coverage, 3),
                        sensors_used=sensory.sensors_used,
                        nearby_transport=nearby_transport,
                        geometry=generated_route.geojson,
                    )
                )
        return RouteResponse(routes=route_options)

