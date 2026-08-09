"""Crowd estimation and Dijkstra routing over the loaded network."""

from __future__ import annotations

import heapq
import math
from dataclasses import dataclass
from typing import Callable

from app.config import CROWD_WEIGHT_SECONDS, UNKNOWN_CROWD_PENALTY
from app.services.data_service import Arc, DataRepository


def congestion_level(score: float) -> str:
    if score >= 100:
        return "HIGH"
    if score >= 50:
        return "MEDIUM"
    return "LOW"


@dataclass(frozen=True)
class CrowdValue:
    score: float
    level: str
    source: str
    is_unknown: bool
    observation_status: str | None
    coverage_status: str | None
    as_of: str | None
    sensory_indicator: str | None


@dataclass(frozen=True)
class PathResult:
    arcs: list[Arc]


class RoutingService:
    def __init__(self, repository: DataRepository):
        self.repository = repository

    def crowd_for_edge(self, edge_id: str, weekday_index: int, local_hour: int) -> CrowdValue:
        context = self.repository.contexts.get(edge_id)
        if (
            context
            and context.observation_status == "CURRENT"
            and context.coverage_status == "OBSERVED"
            and context.crowd_count is not None
        ):
            return CrowdValue(
                score=context.crowd_count,
                level=context.crowd_level or congestion_level(context.crowd_count),
                source="current_observation",
                is_unknown=False,
                observation_status=context.observation_status,
                coverage_status=context.coverage_status,
                as_of=context.as_of,
                sensory_indicator=context.sensory_indicator,
            )
        pattern = self.repository.patterns.get((edge_id, weekday_index, local_hour))
        if pattern:
            return CrowdValue(
                score=pattern.mean_count,
                level=congestion_level(pattern.mean_count),
                source="historical_pattern",
                is_unknown=False,
                observation_status=context.observation_status if context else None,
                coverage_status=context.coverage_status if context else None,
                as_of=context.as_of if context else None,
                sensory_indicator=context.sensory_indicator if context else None,
            )
        return CrowdValue(
            score=UNKNOWN_CROWD_PENALTY,
            level="UNKNOWN",
            source="unknown",
            is_unknown=True,
            observation_status=context.observation_status if context else None,
            coverage_status=context.coverage_status if context else None,
            as_of=context.as_of if context else None,
            sensory_indicator=context.sensory_indicator if context else None,
        )

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

    def route_summary(self, path: PathResult, route_type: str, weekday_index: int, local_hour: int) -> dict:
        edge_ids = [arc.edge_id for arc in path.arcs]
        edges = [self.repository.edges[edge_id] for edge_id in edge_ids]
        crowds = [self.crowd_for_edge(edge_id, weekday_index, local_hour) for edge_id in edge_ids]
        coordinates: list[list[float]] = []
        for edge, arc in zip(edges, path.arcs):
            line = edge.geometry.get("coordinates", [])
            if arc.traverses_reverse:
                line = list(reversed(line))
            if not coordinates:
                coordinates.extend(line)
            elif line:
                coordinates.extend(line[1:])
        return {
            "route_type": route_type,
            "edge_ids": edge_ids,
            "distance_m": round(sum(edge.length_m for edge in edges), 2),
            "walk_time_seconds": round(sum(edge.walk_seconds for edge in edges), 2),
            "crowd_exposure": round(sum(value.score for value in crowds), 2),
            "unknown_edge_count": sum(value.is_unknown for value in crowds),
            "geometry": {"type": "LineString", "coordinates": coordinates},
        }
