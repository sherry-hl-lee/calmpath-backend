"""Read-only repository backed by the FIT5120 MySQL RDS data contract."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
import json
from typing import Iterator, Optional

import pymysql
from pymysql.cursors import DictCursor

from app.core.routing_config import DatabaseSettings


class DataError(RuntimeError):
    """Raised when the RDS data contract cannot be read safely."""


@dataclass(frozen=True)
class Node:
    node_id: str
    latitude: float
    longitude: float


@dataclass(frozen=True)
class Edge:
    edge_id: str
    from_node_id: str
    to_node_id: str
    length_m: float
    walk_seconds: float
    is_bidirectional: bool
    street_name: Optional[str]
    between_street_1: Optional[str]
    between_street_2: Optional[str]
    geometry: dict


@dataclass(frozen=True)
class Arc:
    edge_id: str
    to_node_id: str
    walk_seconds: float
    traverses_reverse: bool = False


@dataclass(frozen=True)
class HistoricalPattern:
    mean_count: float
    sample_count: int
    minimum_count: float
    maximum_count: float


@dataclass(frozen=True)
class CurrentContext:
    crowd_count: Optional[float]
    crowd_level: Optional[str]
    sensory_indicator: Optional[str]
    observation_status: str
    coverage_status: str
    as_of: Optional[str]
    source_observed_at: Optional[str]
    sensor_count: int
    aggregation_method: Optional[str]


def _optional_text(value: Optional[str]) -> Optional[str]:
    return value.strip() if value and value.strip() else None


def _geojson(value: object) -> dict:
    if isinstance(value, dict):
        return value
    if isinstance(value, (bytes, bytearray)):
        value = value.decode("utf-8")
    return json.loads(str(value))


def _utc_iso(value: object) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    return str(value)


class RdsRepository:
    """Loads the routing graph once and refreshes live sensor observations per request.

    The graph and hourly patterns are baseline data. Current values are derived
    from ``clean_pedestrian_minute`` because the contract states that the
    materialised ``backend_edge_sensory_context_current`` table is not refreshed
    by the 15-minute job.
    """

    def __init__(self, settings: DatabaseSettings):
        self.settings = settings
        self.nodes: dict[str, Node] = {}
        self.edges: dict[str, Edge] = {}
        self.adjacency: dict[str, list[Arc]] = {}
        self.patterns: dict[tuple[str, int, int], HistoricalPattern] = {}
        self.contexts: dict[str, CurrentContext] = {}
        self.sensor_mapped_edge_ids: set[str] = set()

    @contextmanager
    def _connection(self) -> Iterator[object]:
        options = {
            "host": self.settings.host,
            "port": self.settings.port,
            "user": self.settings.user,
            "password": self.settings.password,
            "database": self.settings.database,
            "charset": "utf8mb4",
            "cursorclass": DictCursor,
            "autocommit": True,
            "connect_timeout": self.settings.connect_timeout_seconds,
            "read_timeout": self.settings.connect_timeout_seconds,
        }
        if self.settings.ssl_ca:
            options["ssl"] = {"ca": self.settings.ssl_ca}
        try:
            connection = pymysql.connect(**options)
            with connection.cursor() as cursor:
                cursor.execute("SET time_zone = '+00:00'")
            yield connection
        except pymysql.MySQLError as error:
            raise DataError("Unable to read the FIT5120 MySQL RDS database.") from error
        finally:
            if "connection" in locals():
                connection.close()

    def load(self) -> None:
        """Load immutable routing data required by the in-memory route solver."""
        with self._connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT node_id, latitude, longitude FROM backend_routing_nodes"
                )
                for row in cursor.fetchall():
                    node = Node(
                        node_id=row["node_id"],
                        latitude=float(row["latitude"]),
                        longitude=float(row["longitude"]),
                    )
                    self.nodes[node.node_id] = node

                cursor.execute(
                    """
                    SELECT edge_id, from_node_id, to_node_id, length_m,
                           base_walk_cost_seconds, is_bidirectional,
                           street_name, between_street_1, between_street_2,
                           geometry_geojson
                    FROM backend_routing_edges
                    """
                )
                for row in cursor.fetchall():
                    edge = Edge(
                        edge_id=row["edge_id"],
                        from_node_id=row["from_node_id"],
                        to_node_id=row["to_node_id"],
                        length_m=float(row["length_m"]),
                        walk_seconds=float(row["base_walk_cost_seconds"]),
                        is_bidirectional=bool(row["is_bidirectional"]),
                        street_name=_optional_text(row["street_name"]),
                        between_street_1=_optional_text(row["between_street_1"]),
                        between_street_2=_optional_text(row["between_street_2"]),
                        geometry=_geojson(row["geometry_geojson"]),
                    )
                    if edge.from_node_id not in self.nodes or edge.to_node_id not in self.nodes:
                        raise DataError(f"RDS edge {edge.edge_id} references a missing node.")
                    self.edges[edge.edge_id] = edge
                    self.adjacency.setdefault(edge.from_node_id, []).append(
                        Arc(edge.edge_id, edge.to_node_id, edge.walk_seconds)
                    )
                    if edge.is_bidirectional:
                        self.adjacency.setdefault(edge.to_node_id, []).append(
                            Arc(edge.edge_id, edge.from_node_id, edge.walk_seconds, traverses_reverse=True)
                        )

                cursor.execute(
                    """
                    SELECT edge_id, weekday_index, local_hour, sample_count,
                           mean_count, minimum_count, maximum_count
                    FROM backend_edge_hourly_patterns
                    """
                )
                for row in cursor.fetchall():
                    key = (row["edge_id"], int(row["weekday_index"]), int(row["local_hour"]))
                    self.patterns[key] = HistoricalPattern(
                        mean_count=float(row["mean_count"]),
                        sample_count=int(row["sample_count"]),
                        minimum_count=float(row["minimum_count"]),
                        maximum_count=float(row["maximum_count"]),
                    )

                cursor.execute(
                    "SELECT DISTINCT edge_id FROM backend_sensor_edge_map WHERE edge_id IS NOT NULL"
                )
                self.sensor_mapped_edge_ids = {row["edge_id"] for row in cursor.fetchall()}

        if not self.nodes or not self.edges:
            raise DataError("RDS routing nodes and edges must not be empty.")
        self.refresh_current_contexts()

    def refresh_current_contexts(self) -> None:
        """Derive fresh edge observations from the 15-minute minute-count table.

        For an edge with more than one current mapped sensor, the maximum current
        ``count_total`` is used. Crowd-avoidance routing should not hide a busy
        part of an edge by averaging it with a quiet nearby sensor.
        """
        query = """
            WITH latest_observation AS (
                SELECT location_id, MAX(observed_at_utc) AS observed_at_utc
                FROM clean_pedestrian_minute
                WHERE observed_at_utc <= UTC_TIMESTAMP()
                GROUP BY location_id
            ),
            latest_count AS (
                SELECT p.location_id, p.observed_at_utc, p.count_total
                FROM clean_pedestrian_minute AS p
                JOIN latest_observation AS latest
                  ON latest.location_id = p.location_id
                 AND latest.observed_at_utc = p.observed_at_utc
            ),
            edge_freshness AS (
                SELECT
                    map.edge_id,
                    MIN(TIMESTAMPDIFF(
                        SECOND, counts.observed_at_utc, UTC_TIMESTAMP()
                    )) AS newest_age_seconds
                FROM backend_sensor_edge_map AS map
                LEFT JOIN latest_count AS counts
                  ON counts.location_id = map.location_id
                WHERE map.edge_id IS NOT NULL
                GROUP BY map.edge_id
            ),
            current_sensor AS (
                SELECT
                    map.edge_id,
                    map.location_id,
                    counts.observed_at_utc,
                    counts.count_total
                FROM backend_sensor_edge_map AS map
                JOIN latest_count AS counts
                  ON counts.location_id = map.location_id
                WHERE map.edge_id IS NOT NULL
                  AND counts.observed_at_utc >= UTC_TIMESTAMP() - INTERVAL 30 MINUTE
            ),
            current_edge_statistics AS (
                SELECT
                    edge_id,
                    COUNT(DISTINCT location_id) AS current_sensor_count,
                    MAX(count_total) AS current_crowd_count
                FROM current_sensor
                GROUP BY edge_id
            ),
            current_edge AS (
                SELECT
                    statistics.edge_id,
                    statistics.current_sensor_count,
                    statistics.current_crowd_count,
                    MAX(sensor.observed_at_utc) AS source_observed_at
                FROM current_edge_statistics AS statistics
                JOIN current_sensor AS sensor
                  ON sensor.edge_id = statistics.edge_id
                 AND sensor.count_total = statistics.current_crowd_count
                GROUP BY
                    statistics.edge_id,
                    statistics.current_sensor_count,
                    statistics.current_crowd_count
            )
            SELECT
                freshness.edge_id,
                current.source_observed_at,
                freshness.newest_age_seconds,
                COALESCE(current.current_sensor_count, 0) AS current_sensor_count,
                current.current_crowd_count
            FROM edge_freshness AS freshness
            LEFT JOIN current_edge AS current
              ON current.edge_id = freshness.edge_id
        """
        contexts: dict[str, CurrentContext] = {}
        with self._connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(query)
                rows = cursor.fetchall()

        evaluated_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        for row in rows:
            current_sensor_count = int(row["current_sensor_count"] or 0)
            newest_age_seconds = row["newest_age_seconds"]
            if current_sensor_count:
                observation_status = "CURRENT"
                coverage_status = "OBSERVED"
                crowd_count = float(row["current_crowd_count"])
            elif newest_age_seconds is not None and newest_age_seconds <= 3600:
                observation_status = "STALE"
                coverage_status = "STALE_OBSERVATION"
                crowd_count = None
            else:
                observation_status = "UNAVAILABLE"
                coverage_status = "UNAVAILABLE_OBSERVATION"
                crowd_count = None
            contexts[row["edge_id"]] = CurrentContext(
                crowd_count=crowd_count,
                crowd_level=None,
                sensory_indicator=None,
                observation_status=observation_status,
                coverage_status=coverage_status,
                as_of=evaluated_at,
                source_observed_at=_utc_iso(row["source_observed_at"]),
                sensor_count=current_sensor_count,
                aggregation_method="maximum" if current_sensor_count else None,
            )
        self.contexts = contexts
