from dataclasses import dataclass

import httpx

from app.core.config import ORS_API_KEY, ORS_BASE_URL
from app.services.route_geometry import Coordinate


class RoutingProviderError(RuntimeError):
    pass


@dataclass(frozen=True)
class GeneratedRoute:
    id: str
    distance_m: float
    duration_s: float
    coordinates: list[Coordinate]

    @property
    def geojson(self) -> dict[str, object]:
        return {
            "type": "LineString",
            "coordinates": [
                [coordinate.longitude, coordinate.latitude]
                for coordinate in self.coordinates
            ],
        }


class OpenRouteServiceProvider:
    async def generate(
        self,
        client: httpx.AsyncClient,
        origin: Coordinate,
        destination: Coordinate,
    ) -> list[GeneratedRoute]:
        if not ORS_API_KEY:
            raise RoutingProviderError("Walking route provider is not configured")

        response = await client.post(
            ORS_BASE_URL,
            headers={
                "Authorization": ORS_API_KEY,
                "Content-Type": "application/json",
            },
            json={
                "coordinates": [
                    [origin.longitude, origin.latitude],
                    [destination.longitude, destination.latitude],
                ],
                "alternative_routes": {
                    "target_count": 3,
                    "share_factor": 0.65,
                    "weight_factor": 1.5,
                },
                "instructions": False,
            },
        )
        if response.status_code >= 400:
            raise RoutingProviderError(
                f"Walking route provider returned HTTP {response.status_code}"
            )

        routes: list[GeneratedRoute] = []
        for index, feature in enumerate(response.json().get("features", []), start=1):
            raw_coordinates = feature.get("geometry", {}).get("coordinates", [])
            summary = feature.get("properties", {}).get("summary", {})
            if len(raw_coordinates) < 2:
                continue
            routes.append(
                GeneratedRoute(
                    id=f"route-{index}",
                    distance_m=float(summary.get("distance", 0)),
                    duration_s=float(summary.get("duration", 0)),
                    coordinates=[
                        Coordinate(latitude=float(latitude), longitude=float(longitude))
                        for longitude, latitude, *_ in raw_coordinates
                    ],
                )
            )

        if not routes:
            raise RoutingProviderError("Walking route provider returned no routes")
        return routes

