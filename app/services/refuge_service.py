import json
import math
from pathlib import Path

from app.schemas.refuge import Refuge


class RefugeService:
    def __init__(self) -> None:
        self._data_path = Path(__file__).resolve().parents[1] / "data" / "mock_refuges.json"

    def find_nearby(self, latitude: float, longitude: float, radius_m: int) -> list[Refuge]:
        with self._data_path.open(encoding="utf-8") as file:
            refuges = json.load(file)

        nearby_refuges = []
        for refuge in refuges:
            distance_m = self._haversine_distance(
                latitude,
                longitude,
                refuge["latitude"],
                refuge["longitude"],
            )
            if distance_m <= radius_m:
                nearby_refuges.append(
                    Refuge(
                        id=refuge["id"],
                        name=refuge["name"],
                        type=refuge["type"],
                        distance_m=round(distance_m, 2),
                        latitude=refuge["latitude"],
                        longitude=refuge["longitude"],
                        address=refuge["address"],
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
