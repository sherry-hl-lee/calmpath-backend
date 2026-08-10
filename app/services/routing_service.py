"""Crowd estimation and Dijkstra routing over the loaded network."""

from __future__ import annotations

import heapq
import math
from dataclasses import dataclass
from typing import Callable

from app.core.routing_config import (
    CROWD_LOW_MAX_PER_MINUTE,
    CROWD_MEDIUM_MAX_PER_MINUTE,
    CROWD_SCORE_UNIT,
    CROWD_THRESHOLD_VERSION,
    CROWD_WEIGHT_SECONDS,
    HISTORICAL_COUNT_INTERVAL_MINUTES,
    MINIMUM_CROWD_COVERAGE_FOR_RECOMMENDATION,
    SENSORY_LEVEL_BASIS,
    UNKNOWN_CROWD_PENALTY,
)
from app.services.data_service import Arc, RdsRepository


def congestion_level(score: float) -> str:
    """Classify a pedestrians-per-minute value using the v1 prototype rule."""

    if score <= CROWD_LOW_MAX_PER_MINUTE:
        return "LOW"
    if score <= CROWD_MEDIUM_MAX_PER_MINUTE:
        return "MEDIUM"
    return "HIGH"


@dataclass(frozen=True)
class CrowdValue:
    score: float
    level: str
    source: str
    is_unknown: bool
    observation_status: str | None
    coverage_status: str | None
    evaluated_at: str | None
    observed_at: str | None
    sensor_count: int | None
    aggregation_method: str | None
    sensory_indicator: str | None


@dataclass(frozen=True)
class PathResult:
    arcs: list[Arc]


class RoutingService:
    def __init__(self, repository: RdsRepository):
        self.repository = repository

    def crowd_for_edge(
        self, edge_id: str, weekday_index: int, local_hour: int, use_current: bool = True
    ) -> CrowdValue:
        context = self.repository.contexts.get(edge_id)
        if (
            use_current
            and
            context
            and context.observation_status == "CURRENT"
            and context.coverage_status == "OBSERVED"
            and context.crowd_count is not None
        ):
            return CrowdValue(
                score=context.crowd_count,
                # Reclassify from the normalized count so an upstream value
                # produced under an older threshold version cannot override
                # this API contract.
                level=congestion_level(context.crowd_count),
                source="current_observation",
                is_unknown=False,
                observation_status=context.observation_status,
                coverage_status=context.coverage_status,
                evaluated_at=context.as_of,
                observed_at=context.source_observed_at,
                sensor_count=context.sensor_count,
                aggregation_method=context.aggregation_method,
                sensory_indicator=context.sensory_indicator,
            )
        pattern = self.repository.patterns.get((edge_id, weekday_index, local_hour))
        if pattern:
            fallback_context = context if use_current else None
            # Historical patterns are means of hourly totals. Convert them to
            # the same pedestrians-per-minute unit as live minute observations
            # before classification, route search, or exposure calculation.
            historical_per_minute = (
                pattern.mean_count / HISTORICAL_COUNT_INTERVAL_MINUTES
            )
            return CrowdValue(
                score=historical_per_minute,
                level=congestion_level(historical_per_minute),
                source="historical_pattern",
                is_unknown=False,
                observation_status=(
                    fallback_context.observation_status if fallback_context else None
                ),
                coverage_status=(
                    fallback_context.coverage_status
                    if fallback_context
                    else "HISTORICAL_PATTERN"
                ),
                evaluated_at=fallback_context.as_of if fallback_context else None,
                observed_at=None,
                sensor_count=None,
                aggregation_method=None,
                sensory_indicator=(
                    fallback_context.sensory_indicator if fallback_context else None
                ),
            )
        fallback_context = context if use_current else None
        return CrowdValue(
            score=UNKNOWN_CROWD_PENALTY,
            level="UNKNOWN",
            source="unknown",
            is_unknown=True,
            observation_status=(
                fallback_context.observation_status if fallback_context else None
            ),
            coverage_status=(
                fallback_context.coverage_status
                if fallback_context
                else "NO_HISTORICAL_PATTERN" if not use_current else "NO_SENSOR_COVERAGE"
            ),
            evaluated_at=fallback_context.as_of if fallback_context else None,
            observed_at=None,
            sensor_count=None,
            aggregation_method=None,
            sensory_indicator=(
                fallback_context.sensory_indicator if fallback_context else None
            ),
        )

    def sensory_cost(
        self,
        arc: Arc,
        weekday_index: int,
        local_hour: int,
        use_current: bool,
    ) -> float:
        """Combine walking time with a distance-scaled crowd cost.

        Scaling by edge length prevents network segmentation from multiplying a
        crowd score simply because one street was split into more graph edges.
        """

        crowd = self.crowd_for_edge(arc.edge_id, weekday_index, local_hour, use_current)
        edge = self.repository.edges[arc.edge_id]
        crowd_seconds = crowd.score * CROWD_WEIGHT_SECONDS * edge.length_m / 1000.0
        return arc.walk_seconds + crowd_seconds

    def nearest_node(self, latitude: float, longitude: float) -> str:
        # The network is loaded once; a simple nearest-node scan is reliable for
        # this prototype. Replace with a spatial index if query volume grows.
        best_id = None
        best_distance = math.inf
        for node in self.repository.nodes.values():
            distance = (node.latitude - latitude) ** 2 + (node.longitude - longitude) ** 2
            if distance < best_distance:
                best_id, best_distance = node.node_id, distance
        assert best_id is not None
        return best_id

    def shortest_path(self, start: str, end: str, weight: Callable[[Arc], float]) -> PathResult:
        if start not in self.repository.nodes or end not in self.repository.nodes:
            raise ValueError("Origin or destination node does not exist in the routing network.")
        queue: list[tuple[float, str]] = [(0.0, start)]
        distances = {start: 0.0}
        previous: dict[str, tuple[str, Arc]] = {}
        while queue:
            cost, node_id = heapq.heappop(queue)
            if cost != distances.get(node_id):
                continue
            if node_id == end:
                break
            for arc in self.repository.adjacency.get(node_id, []):
                next_cost = cost + weight(arc)
                if next_cost < distances.get(arc.to_node_id, math.inf):
                    distances[arc.to_node_id] = next_cost
                    previous[arc.to_node_id] = (node_id, arc)
                    heapq.heappush(queue, (next_cost, arc.to_node_id))
        if end not in distances:
            raise ValueError("No walkable route exists between the supplied locations.")
        arcs: list[Arc] = []
        node_id = end
        while node_id != start:
            node_id, arc = previous[node_id]
            arcs.append(arc)
        arcs.reverse()
        return PathResult(arcs)

    def route_summary(
        self,
        path: PathResult,
        route_type: str,
        weekday_index: int,
        local_hour: int,
        use_current: bool,
    ) -> dict:
        edge_ids = [arc.edge_id for arc in path.arcs]
        edges = [self.repository.edges[edge_id] for edge_id in edge_ids]
        crowds = [
            self.crowd_for_edge(edge_id, weekday_index, local_hour, use_current)
            for edge_id in edge_ids
        ]
        coordinates: list[list[float]] = []
        segments: list[dict] = []
        for sequence, (edge, arc, crowd) in enumerate(
            zip(edges, path.arcs, crowds), start=1
        ):
            line = edge.geometry.get("coordinates", [])
            if arc.traverses_reverse:
                line = list(reversed(line))
            segment_geometry = {"type": "LineString", "coordinates": line}
            segments.append(
                {
                    "edge_id": edge.edge_id,
                    "sequence": sequence,
                    "street_name": edge.street_name,
                    "distance_m": round(edge.length_m, 2),
                    "walk_time_seconds": round(edge.walk_seconds, 2),
                    "crowd_score": None if crowd.is_unknown else round(crowd.score, 2),
                    "crowd_score_unit": CROWD_SCORE_UNIT,
                    "routing_penalty": round(crowd.score, 2) if crowd.is_unknown else None,
                    "crowd_level": crowd.level,
                    # Until independent sensory inputs exist, the segment
                    # sensory level is explicitly derived from crowd level.
                    "sensory_level": crowd.level,
                    "limited_data": crowd.is_unknown,
                    "congestion_level": crowd.level,
                    "crowd_source": crowd.source,
                    "observation_status": crowd.observation_status,
                    "coverage_status": crowd.coverage_status,
                    "evaluated_at": crowd.evaluated_at,
                    "observed_at": crowd.observed_at,
                    "sensor_count": crowd.sensor_count,
                    "aggregation_method": crowd.aggregation_method,
                    "geometry": segment_geometry,
                }
            )
            if not coordinates:
                coordinates.extend(line)
            elif line:
                coordinates.extend(line[1:])
        total_distance = sum(edge.length_m for edge in edges)
        known_pairs = [
            (edge, crowd)
            for edge, crowd in zip(edges, crowds)
            if not crowd.is_unknown
        ]
        known_distance = sum(edge.length_m for edge, _ in known_pairs)
        crowd_exposure = (
            sum(edge.length_m * crowd.score for edge, crowd in known_pairs) / known_distance
            if known_distance
            else None
        )
        data_coverage_ratio = known_distance / total_distance if total_distance else 0.0
        limited_data = (
            data_coverage_ratio < MINIMUM_CROWD_COVERAGE_FOR_RECOMMENDATION
        )
        route_crowd_level = (
            congestion_level(crowd_exposure)
            if crowd_exposure is not None and not limited_data
            else None
        )
        return {
            "route_type": route_type,
            "edge_ids": edge_ids,
            "distance_m": round(total_distance, 2),
            "walk_time_seconds": round(sum(edge.walk_seconds for edge in edges), 2),
            "crowd_exposure": crowd_exposure,
            "crowd_exposure_unit": CROWD_SCORE_UNIT,
            "crowd_exposure_range": {"minimum": 0.0, "maximum": None},
            "crowd_level": route_crowd_level,
            "sensory_level": route_crowd_level,
            "sensory_level_basis": SENSORY_LEVEL_BASIS,
            "limited_data": limited_data,
            "minimum_required_coverage_ratio": MINIMUM_CROWD_COVERAGE_FOR_RECOMMENDATION,
            "crowd_threshold_version": CROWD_THRESHOLD_VERSION,
            "routing_crowd_cost": round(
                sum(
                    edge.length_m * crowd.score * CROWD_WEIGHT_SECONDS / 1000.0
                    for edge, crowd in zip(edges, crowds)
                ),
                2,
            ),
            "known_edge_count": sum(not value.is_unknown for value in crowds),
            "unknown_edge_count": sum(value.is_unknown for value in crowds),
            "known_distance_m": round(known_distance, 2),
            "unknown_distance_m": round(max(total_distance - known_distance, 0.0), 2),
            "total_distance_m": round(total_distance, 2),
            "data_coverage_ratio": data_coverage_ratio,
            "congested_segment_count": sum(value.level == "HIGH" for value in crowds),
            "has_congestion_warning": any(value.level == "HIGH" for value in crowds),
            "segments": segments,
            "geometry": {"type": "LineString", "coordinates": coordinates},
        }
