"""Deterministic local repository for API integration without MySQL RDS."""

from __future__ import annotations

from app.services.data_service import (
    Arc,
    CurrentContext,
    Edge,
    HistoricalPattern,
    Node,
)


class FakeRepository:
    """Small graph implementing the same repository surface as RdsRepository.

    The shorter path is deliberately crowded and the longer path is quiet so
    local frontend integration can exercise a real LOWER_CROWD response. This
    repository is selected only when DATA_SOURCE=fake and never opens MySQL.
    """

    def __init__(self) -> None:
        self.nodes: dict[str, Node] = {}
        self.edges: dict[str, Edge] = {}
        self.adjacency: dict[str, list[Arc]] = {}
        self.patterns: dict[tuple[str, int, int], HistoricalPattern] = {}
        self.contexts: dict[str, CurrentContext] = {}
        self.sensor_mapped_edge_ids: set[str] = set()

    @staticmethod
    def _edge(
        edge_id: str,
        start: str,
        end: str,
        length_m: float,
        walk_seconds: float,
        points: dict[str, list[float]],
    ) -> Edge:
        return Edge(
            edge_id=edge_id,
            from_node_id=start,
            to_node_id=end,
            length_m=length_m,
            walk_seconds=walk_seconds,
            is_bidirectional=True,
            street_name=edge_id,
            between_street_1=None,
            between_street_2=None,
            geometry={"type": "LineString", "coordinates": [points[start], points[end]]},
        )

    def load(self) -> None:
        points = {
            "origin": [144.963, -37.813],
            "short_mid": [144.958, -37.816],
            "quiet_mid": [144.968, -37.816],
            "destination": [144.950, -37.820],
        }
        self.nodes = {
            node_id: Node(node_id, coordinates[1], coordinates[0])
            for node_id, coordinates in points.items()
        }
        self.edges = {
            "short_1": self._edge("short_1", "origin", "short_mid", 500, 300, points),
            "short_2": self._edge("short_2", "short_mid", "destination", 500, 300, points),
            "quiet_1": self._edge("quiet_1", "origin", "quiet_mid", 700, 420, points),
            "quiet_2": self._edge("quiet_2", "quiet_mid", "destination", 700, 420, points),
        }
        self.adjacency = {
            "origin": [
                Arc("short_1", "short_mid", 300),
                Arc("quiet_1", "quiet_mid", 420),
            ],
            "short_mid": [
                Arc("short_1", "origin", 300, traverses_reverse=True),
                Arc("short_2", "destination", 300),
            ],
            "quiet_mid": [
                Arc("quiet_1", "origin", 420, traverses_reverse=True),
                Arc("quiet_2", "destination", 420),
            ],
            "destination": [
                Arc("short_2", "short_mid", 300, traverses_reverse=True),
                Arc("quiet_2", "quiet_mid", 420, traverses_reverse=True),
            ],
        }

        # HistoricalPattern stores hourly totals. The routing service converts
        # these values to the same per-minute unit used by current observations.
        for weekday_index in range(7):
            for local_hour in range(24):
                self.patterns[("short_1", weekday_index, local_hour)] = HistoricalPattern(
                    24000, 5, 23000, 25000
                )
                self.patterns[("short_2", weekday_index, local_hour)] = HistoricalPattern(
                    24000, 5, 23000, 25000
                )
                self.patterns[("quiet_1", weekday_index, local_hour)] = HistoricalPattern(
                    600, 5, 300, 900
                )
                self.patterns[("quiet_2", weekday_index, local_hour)] = HistoricalPattern(
                    600, 5, 300, 900
                )

        self.sensor_mapped_edge_ids = set(self.edges)
        self.refresh_current_contexts()

    def refresh_current_contexts(self) -> None:
        # Synthetic fixture data must never masquerade as a current City of
        # Melbourne observation. Full 7x24 historical patterns above keep the
        # local API deterministic while current_data_used remains false.
        self.contexts = {}
