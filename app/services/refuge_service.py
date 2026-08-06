import csv
import math
from pathlib import Path

from app.core.config import REFUGE_DATA_PATH
from app.schemas.refuge import NearbyRefuge


TYPE_BY_SUB_THEME = {
    "Informal Outdoor Facility (Park/Garden/Reserve)": "park",
    "Library": "library",
}
REQUIRED_CSV_FIELDS = {
    "landmark_id",
    "feature_name",
    "sub_theme",
    "latitude",
    "longitude",
    "is_refuge_candidate",
}


class RefugeService:
    def __init__(self, data_path: Path | None = None) -> None:
        self._data_path = data_path or REFUGE_DATA_PATH

    def find_nearby(self, latitude: float, longitude: float, radius_m: float) -> list[NearbyRefuge]:
        with self._data_path.open(encoding="utf-8", newline="") as file:
            reader = csv.DictReader(file)
            fieldnames = set(reader.fieldnames or [])
            missing_fields = REQUIRED_CSV_FIELDS - fieldnames
            if missing_fields:
                missing = ", ".join(sorted(missing_fields))
                raise ValueError(f"Refuge CSV is missing required fields: {missing}")

            refuges = [
                refuge
                for refuge in reader
                if refuge["is_refuge_candidate"].strip().lower() == "true"
            ]

        nearby_refuges: list[NearbyRefuge] = []
        for refuge in refuges:
            refuge_type = TYPE_BY_SUB_THEME.get(refuge["sub_theme"].strip())
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
                        id=refuge["landmark_id"],
                        name=refuge["feature_name"],
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
