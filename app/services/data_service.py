"""CSV-backed network repository loaded once when the API starts."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


class DataError(RuntimeError):
    pass


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


def _optional_text(value: Optional[str]) -> Optional[str]:
    return value.strip() if value and value.strip() else None


def _optional_float(value: Optional[str]) -> Optional[float]:
    text = _optional_text(value)
    return float(text) if text is not None else None


def _read_rows(path: Path):
    if not path.exists():
        raise DataError(f"Required data file is missing: {path}")
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        yield from csv.DictReader(handle)


class DataRepository:
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.nodes: dict[str, Node] = {}
        self.edges: dict[str, Edge] = {}
        self.adjacency: dict[str, list[Arc]] = {}
        self.patterns: dict[tuple[str, int, int], HistoricalPattern] = {}
        self.contexts: dict[str, CurrentContext] = {}

    def load(self) -> None:
        self._load_nodes()
        self._load_edges()
        self._load_patterns()
        self._load_contexts()
        if not self.nodes or not self.edges:
            raise DataError("Routing nodes and edges must not be empty.")

    def _load_nodes(self) -> None:
        for row in _read_rows(self.data_dir / "routing_nodes.csv"):
            node = Node(
                node_id=row["node_id"],
                latitude=float(row["latitude"]),
                longitude=float(row["longitude"]),
            )
            self.nodes[node.node_id] = node

    def _load_edges(self) -> None:
        for row in _read_rows(self.data_dir / "routing_edges.csv"):
            edge = Edge(
                edge_id=row["edge_id"],
                from_node_id=row["from_node_id"],
                to_node_id=row["to_node_id"],
                length_m=float(row["length_m"]),
                walk_seconds=float(row["base_walk_cost_seconds"]),
                is_bidirectional=row["is_bidirectional"].strip().lower() in {"true", "1", "yes"},
                street_name=_optional_text(row.get("street_name")),
                between_street_1=_optional_text(row.get("between_street_1")),
                between_street_2=_optional_text(row.get("between_street_2")),
                geometry=json.loads(row["geometry_geojson"]),
            )
            if edge.from_node_id not in self.nodes or edge.to_node_id not in self.nodes:
                raise DataError(f"Edge {edge.edge_id} references a missing node.")
            self.edges[edge.edge_id] = edge
            self.adjacency.setdefault(edge.from_node_id, []).append(
                Arc(edge.edge_id, edge.to_node_id, edge.walk_seconds)
            )
            if edge.is_bidirectional:
                self.adjacency.setdefault(edge.to_node_id, []).append(
                    Arc(edge.edge_id, edge.from_node_id, edge.walk_seconds, traverses_reverse=True)
                )

    def _load_patterns(self) -> None:
        for row in _read_rows(self.data_dir / "edge_hourly_patterns.csv"):
            edge_id = row["edge_id"]
            if edge_id not in self.edges:
                continue
            key = (edge_id, int(row["weekday_index"]), int(row["local_hour"]))
            self.patterns[key] = HistoricalPattern(
                mean_count=float(row["mean_count"]),
                sample_count=int(row["sample_count"]),
                minimum_count=float(row["minimum_count"]),
                maximum_count=float(row["maximum_count"]),
            )

    def _load_contexts(self) -> None:
        for row in _read_rows(self.data_dir / "edge_sensory_context_current.csv"):
            edge_id = row["edge_id"]
            if edge_id not in self.edges:
                continue
            self.contexts[edge_id] = CurrentContext(
                crowd_count=_optional_float(row.get("crowd_count")),
                crowd_level=_optional_text(row.get("crowd_level")),
                sensory_indicator=_optional_text(row.get("sensory_indicator")),
                observation_status=row["observation_status"],
                coverage_status=row["coverage_status"],
                as_of=_optional_text(row.get("as_of")),
                source_observed_at=_optional_text(row.get("source_observed_at")),
            )
