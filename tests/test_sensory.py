import pytest

from app.schemas.route import SensoryIndicator
from app.services.route_geometry import Coordinate
from app.services.sensory_service import (
    CURRENT_SENSOR_QUERY,
    PedestrianSensor,
    RdsSensoryDataSource,
    SensoryService,
)


class FakeSensoryDataSource:
    def __init__(self, sensors: list[PedestrianSensor], count: float | None) -> None:
        self.sensors = sensors
        self.count = count

    async def active_sensors(self, client) -> list[PedestrianSensor]:
        return self.sensors

    async def latest_count(self, client, sensor_id: str) -> float | None:
        return self.count


class FakeDatabaseClient:
    def __init__(self, rows: list[dict]) -> None:
        self.rows = rows
        self.queries: list[str] = []

    def fetch_all(self, query: str, params=()) -> list[dict]:
        self.queries.append(query)
        return self.rows


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("count", "expected"),
    [
        (800.0, SensoryIndicator.HIGH),
        (300.0, SensoryIndicator.LOW),
    ],
)
async def test_adequately_covered_routes_receive_high_or_low(count, expected) -> None:
    route = [Coordinate(-37.8136, 144.9631)]
    data_source = FakeSensoryDataSource(
        [PedestrianSensor("sensor-1", Coordinate(-37.8136, 144.9631))],
        count,
    )

    assessment = await SensoryService(data_source).assess(None, route)

    assert assessment.indicator == expected
    assert assessment.score == count
    assert assessment.coverage == 1
    assert assessment.sensors_used == 1


@pytest.mark.asyncio
async def test_incomplete_sensor_coverage_returns_limited_data() -> None:
    route = [
        Coordinate(-37.8136, 144.9631),
        Coordinate(-37.8136, 144.9731),
    ]
    data_source = FakeSensoryDataSource(
        [PedestrianSensor("sensor-1", Coordinate(-37.80, 144.90))],
        800,
    )

    assessment = await SensoryService(data_source).assess(None, route)

    assert assessment.indicator == SensoryIndicator.LIMITED_DATA
    assert assessment.score is None
    assert assessment.sensors_used == 0


@pytest.mark.asyncio
async def test_rds_source_maps_latest_fresh_count_and_reuses_cache() -> None:
    database = FakeDatabaseClient(
        [
            {
                "location_id": 42,
                "latitude": -37.8136,
                "longitude": 144.9631,
                "count_total": 725,
                "age_minutes_now": 10,
            }
        ]
    )
    source = RdsSensoryDataSource(database)

    sensors = await source.active_sensors(None)
    count = await source.latest_count(None, "42")

    assert sensors == [PedestrianSensor("42", Coordinate(-37.8136, 144.9631))]
    assert count == 725
    assert len(database.queries) == 1


@pytest.mark.asyncio
async def test_rds_source_treats_stale_count_as_missing() -> None:
    database = FakeDatabaseClient(
        [
            {
                "location_id": "sensor-1",
                "latitude": -37.8136,
                "longitude": 144.9631,
                "count_total": 725,
                "age_minutes_now": 31,
            }
        ]
    )
    source = RdsSensoryDataSource(database)

    await source.active_sensors(None)

    assert await source.latest_count(None, "sensor-1") is None


def test_rds_query_uses_published_tables_and_active_sensor_rule() -> None:
    assert "clean_sensor_locations" in CURRENT_SENSOR_QUERY
    assert "clean_pedestrian_minute" in CURRENT_SENSOR_QUERY
    assert "s.expected_active = 1" in CURRENT_SENSOR_QUERY
    assert "MAX(m_latest.observed_at_utc)" in CURRENT_SENSOR_QUERY
