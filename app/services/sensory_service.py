import asyncio
import time
from dataclasses import dataclass
from statistics import mean
from typing import Protocol

import httpx

from app.core.config import (
    HIGH_SENSORY_THRESHOLD,
    MAX_RECENT_COUNT_AGE_MINUTES,
    MINIMUM_SENSOR_COVERAGE,
    SENSOR_MATCH_RADIUS_M,
    SENSORY_RDS_CACHE_SECONDS,
)
from app.core.database import DatabaseClient, MySQLClient
from app.schemas.route import SensoryIndicator
from app.services.route_geometry import Coordinate, distance_to_route_m


CURRENT_SENSOR_QUERY = """
SELECT s.location_id,
       s.latitude,
       s.longitude,
       m.count_total,
       TIMESTAMPDIFF(MINUTE, m.observed_at_utc, UTC_TIMESTAMP()) AS age_minutes_now
FROM clean_sensor_locations AS s
LEFT JOIN clean_pedestrian_minute AS m
  ON m.location_id = s.location_id
 AND m.observed_at_utc = (
       SELECT MAX(m_latest.observed_at_utc)
       FROM clean_pedestrian_minute AS m_latest
       WHERE m_latest.location_id = s.location_id
 )
WHERE s.expected_active = 1
"""


class SensoryDataError(RuntimeError):
    pass


@dataclass(frozen=True)
class PedestrianSensor:
    id: str
    coordinate: Coordinate


@dataclass(frozen=True)
class SensoryAssessment:
    indicator: SensoryIndicator
    score: float | None
    coverage: float
    sensors_used: int


class SensoryDataSource(Protocol):
    async def active_sensors(self, client: httpx.AsyncClient) -> list[PedestrianSensor]:
        ...

    async def latest_count(
        self,
        client: httpx.AsyncClient,
        sensor_id: str,
    ) -> float | None:
        ...


class RdsSensoryDataSource:
    """Read active sensors and their latest 15-minute publication from RDS."""

    def __init__(self, database_client: DatabaseClient | None = None) -> None:
        self._database_client = database_client or MySQLClient()
        self._sensors: list[PedestrianSensor] = []
        self._counts: dict[str, float | None] = {}
        self._loaded_at = 0.0

    async def _refresh_if_needed(self) -> None:
        if time.monotonic() - self._loaded_at < SENSORY_RDS_CACHE_SECONDS:
            return
        try:
            rows = await asyncio.to_thread(
                self._database_client.fetch_all,
                CURRENT_SENSOR_QUERY,
            )
        except Exception as error:
            raise SensoryDataError("RDS sensory data is unavailable") from error

        sensors: list[PedestrianSensor] = []
        counts: dict[str, float | None] = {}
        for row in rows:
            try:
                sensor_id = str(row["location_id"])
                sensor = PedestrianSensor(
                    id=sensor_id,
                    coordinate=Coordinate(
                        latitude=float(row["latitude"]),
                        longitude=float(row["longitude"]),
                    ),
                )
            except (KeyError, TypeError, ValueError):
                continue

            count = row.get("count_total")
            age_minutes = row.get("age_minutes_now")
            try:
                is_fresh = (
                    count is not None
                    and age_minutes is not None
                    and 0 <= float(age_minutes) <= MAX_RECENT_COUNT_AGE_MINUTES
                )
                counts[sensor_id] = float(count) if is_fresh else None
            except (TypeError, ValueError):
                counts[sensor_id] = None
            sensors.append(sensor)

        self._sensors = sensors
        self._counts = counts
        self._loaded_at = time.monotonic()

    async def active_sensors(self, client: httpx.AsyncClient) -> list[PedestrianSensor]:
        await self._refresh_if_needed()
        return self._sensors

    async def latest_count(
        self,
        client: httpx.AsyncClient,
        sensor_id: str,
    ) -> float | None:
        await self._refresh_if_needed()
        return self._counts.get(sensor_id)


class SensoryService:
    def __init__(self, data_source: SensoryDataSource | None = None) -> None:
        self._data_source = data_source or RdsSensoryDataSource()

    async def assess(
        self,
        client: httpx.AsyncClient,
        route_samples: list[Coordinate],
    ) -> SensoryAssessment:
        sensors = await self._data_source.active_sensors(client)
        nearby_sensors = [
            sensor
            for sensor in sensors
            if distance_to_route_m(sensor.coordinate, route_samples) <= SENSOR_MATCH_RADIUS_M
        ]
        if not route_samples:
            return SensoryAssessment(SensoryIndicator.LIMITED_DATA, None, 0.0, 0)

        covered_samples = sum(
            1
            for sample in route_samples
            if any(
                distance_to_route_m(sensor.coordinate, [sample]) <= SENSOR_MATCH_RADIUS_M
                for sensor in nearby_sensors
            )
        )
        coverage = covered_samples / len(route_samples)
        if coverage < MINIMUM_SENSOR_COVERAGE or not nearby_sensors:
            return SensoryAssessment(SensoryIndicator.LIMITED_DATA, None, coverage, 0)

        counts = await asyncio.gather(
            *[
                self._data_source.latest_count(client, sensor.id)
                for sensor in nearby_sensors
            ]
        )
        valid_counts = [count for count in counts if count is not None]
        if not valid_counts:
            return SensoryAssessment(SensoryIndicator.LIMITED_DATA, None, coverage, 0)

        score = mean(valid_counts)
        indicator = (
            SensoryIndicator.HIGH
            if score >= HIGH_SENSORY_THRESHOLD
            else SensoryIndicator.LOW
        )
        return SensoryAssessment(indicator, round(score, 1), coverage, len(valid_counts))
