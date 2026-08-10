import math
from dataclasses import dataclass


EARTH_RADIUS_M = 6_371_000.0


@dataclass(frozen=True)
class Coordinate:
    latitude: float
    longitude: float


def haversine_m(point_1: Coordinate, point_2: Coordinate) -> float:
    latitude_1 = math.radians(point_1.latitude)
    latitude_2 = math.radians(point_2.latitude)
    latitude_delta = latitude_2 - latitude_1
    longitude_delta = math.radians(point_2.longitude - point_1.longitude)
    haversine = (
        math.sin(latitude_delta / 2) ** 2
        + math.cos(latitude_1)
        * math.cos(latitude_2)
        * math.sin(longitude_delta / 2) ** 2
    )
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(haversine))


def sample_route(coordinates: list[Coordinate], interval_m: float) -> list[Coordinate]:
    if len(coordinates) < 2:
        return coordinates

    samples = [coordinates[0]]
    for start, end in zip(coordinates, coordinates[1:]):
        segment_length = haversine_m(start, end)
        segment_count = max(1, math.ceil(segment_length / interval_m))
        for segment_index in range(1, segment_count + 1):
            fraction = segment_index / segment_count
            samples.append(
                Coordinate(
                    latitude=start.latitude + (end.latitude - start.latitude) * fraction,
                    longitude=start.longitude + (end.longitude - start.longitude) * fraction,
                )
            )
    return samples


def distance_to_route_m(point: Coordinate, route_samples: list[Coordinate]) -> float:
    if not route_samples:
        return math.inf
    return min(haversine_m(point, sample) for sample in route_samples)

