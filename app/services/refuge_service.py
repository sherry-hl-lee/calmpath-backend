import math

from app.core.database import DatabaseClient, MySQLClient
from app.schemas.refuge import NearbyRefuge


TYPE_BY_SUB_THEME = {
    "Informal Outdoor Facility (Park/Garden/Reserve)": "park",
    "Library": "library",
}
NEARBY_QUERY = """
SELECT landmark_id, feature_name, sub_theme, latitude, longitude
FROM backend_refuge_candidates
WHERE is_refuge_candidate = 1
"""


class RefugeService:
    def __init__(self, database_client: DatabaseClient | None = None) -> None:
        self._database_client = database_client or MySQLClient()

    def find_nearby(self, latitude: float, longitude: float, radius_m: float) -> list[NearbyRefuge]:
        refuges = self._database_client.fetch_all(NEARBY_QUERY)

        nearby_refuges: list[NearbyRefuge] = []
        for refuge in refuges:
            refuge_type = TYPE_BY_SUB_THEME.get(str(refuge["sub_theme"]).strip())
            if refuge_type is None:
                continue

            refuge_latitude = float(refuge["latitude"])
            refuge_longitude = float(refuge["longitude"])
            distance_m = self._haversine_distance(
                latitude,
                longitude,
                refuge_latitude,
                refuge_longitude,
            )
            if distance_m <= radius_m:
                nearby_refuges.append(
                    NearbyRefuge(
                        id=str(refuge["landmark_id"]),
                        name=str(refuge["feature_name"]),
                        type=refuge_type,
                        distance_m=round(distance_m, 2),
                        latitude=refuge_latitude,
                        longitude=refuge_longitude,
                    )
                )

        return sorted(nearby_refuges, key=lambda refuge: refuge.distance_m)

    @staticmethod
    def _haversine_distance(
        latitude_1: float,
        longitude_1: float,
        latitude_2: float,
        longitude_2: float,
    ) -> float:
        earth_radius_m = 6_371_000
        latitude_delta = math.radians(latitude_2 - latitude_1)
        longitude_delta = math.radians(longitude_2 - longitude_1)
        latitude_1_radians = math.radians(latitude_1)
        latitude_2_radians = math.radians(latitude_2)

        haversine = (
            math.sin(latitude_delta / 2) ** 2
            + math.cos(latitude_1_radians)
            * math.cos(latitude_2_radians)
            * math.sin(longitude_delta / 2) ** 2
        )
        return 2 * earth_radius_m * math.asin(math.sqrt(haversine))
