from __future__ import annotations

from contextlib import contextmanager

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.config import DatabaseSettings, cors_allowed_origins
from app.main import app as production_app
from app.routes.api import router
from app.services.data_service import (
    Arc,
    CurrentContext,
    Edge,
    HistoricalPattern,
    Node,
    RdsRepository,
)
from app.services.routing_service import PathResult, RoutingService, congestion_level


class FakeRepository:
    """Small deterministic graph used to test US1.2 without MySQL RDS."""

    def __init__(self) -> None:
        self.nodes = {
            "origin": Node("origin", -37.813, 144.963),
            "short_mid": Node("short_mid", -37.816, 144.958),
            "quiet_mid": Node("quiet_mid", -37.816, 144.968),
            "destination": Node("destination", -37.820, 144.950),
        }
        self.edges = {
            "short_1": self._edge("short_1", "origin", "short_mid", 500, 10),
            "short_2": self._edge("short_2", "short_mid", "destination", 500, 10),
            "quiet_1": self._edge("quiet_1", "origin", "quiet_mid", 700, 20),
            "quiet_2": self._edge("quiet_2", "quiet_mid", "destination", 700, 20),
        }
        self.adjacency = {
            "origin": [Arc("short_1", "short_mid", 10), Arc("quiet_1", "quiet_mid", 20)],
            "short_mid": [Arc("short_2", "destination", 10)],
            "quiet_mid": [Arc("quiet_2", "destination", 20)],
        }
        self.patterns = {
            ("short_1", 0, 12): HistoricalPattern(12000, 5, 11000, 13000),
            ("short_2", 0, 12): HistoricalPattern(12000, 5, 11000, 13000),
            ("quiet_1", 0, 12): HistoricalPattern(600, 5, 300, 900),
            ("quiet_2", 0, 12): HistoricalPattern(600, 5, 300, 900),
        }
        self.contexts: dict[str, CurrentContext] = {}
        self.refresh_count = 0

    @staticmethod
    def _edge(edge_id: str, start: str, end: str, length_m: float, seconds: float) -> Edge:
        points = {
            "origin": [144.963, -37.813],
            "short_mid": [144.958, -37.816],
            "quiet_mid": [144.968, -37.816],
            "destination": [144.950, -37.820],
        }
        return Edge(
            edge_id=edge_id,
            from_node_id=start,
            to_node_id=end,
            length_m=length_m,
            walk_seconds=seconds,
            is_bidirectional=False,
            street_name=edge_id,
            between_street_1=None,
            between_street_2=None,
            geometry={"type": "LineString", "coordinates": [points[start], points[end]]},
        )

    def refresh_current_contexts(self) -> None:
        self.refresh_count += 1


def api_client() -> tuple[TestClient, FakeRepository]:
    repository = FakeRepository()
    app = FastAPI()
    app.state.repository = repository
    app.state.routing_service = RoutingService(repository)
    app.include_router(router, prefix="/api/v1")
    return TestClient(app), repository


def route_request(travel_time: str | None = "2025-08-11T12:00:00+10:00") -> dict:
    payload = {
        "origin": {"latitude": -37.813, "longitude": 144.963},
        "destination": {"latitude": -37.820, "longitude": 144.950},
    }
    if travel_time is not None:
        payload["travel_time"] = travel_time
    return payload


def test_route_comparison_returns_frontend_ready_segments_and_status() -> None:
    client, repository = api_client()
    response = client.post("/api/v1/routes/compare", json=route_request())

    assert response.status_code == 200
    body = response.json()
    assert body["current_data_used"] is False
    assert repository.refresh_count == 0
    assert body["recommendation_status"] == "LOWER_CROWD"
    assert body["recommended_route_is_distinct"] is True
    assert body["crowd_exposure_reduction_percent"] == 95.0
    assert body["warning"] == "High pedestrian congestion detected on the shortest route."
    assert body["data_as_of"] is None

    shortest = body["shortest_route"]
    recommended = body["recommended_route"]
    assert shortest["edge_ids"] == ["short_1", "short_2"]
    assert recommended["edge_ids"] == ["quiet_1", "quiet_2"]
    assert recommended["route_type"] == "sensory_recommended"
    assert shortest["crowd_exposure"] == 200.0
    assert recommended["crowd_exposure"] == 10.0
    assert shortest["crowd_exposure_unit"] == "pedestrians_per_minute"
    assert shortest["crowd_exposure_range"] == {"minimum": 0.0, "maximum": None}
    assert shortest["crowd_level"] == "HIGH"
    assert shortest["sensory_level"] == "HIGH"
    assert shortest["sensory_level_basis"] == "PEDESTRIAN_CROWD_ONLY"
    assert shortest["limited_data"] is False
    assert shortest["minimum_required_coverage_ratio"] == 0.6
    assert shortest["crowd_threshold_version"] == "provisional-dmp-v1"
    assert shortest["unknown_distance_m"] == 0.0
    assert recommended["crowd_level"] == "LOW"
    assert shortest["data_coverage_ratio"] == 1.0
    assert shortest["congested_segment_count"] == 2
    assert shortest["has_congestion_warning"] is True

    first_segment = shortest["segments"][0]
    assert first_segment["sequence"] == 1
    assert first_segment["crowd_level"] == "HIGH"
    assert first_segment["sensory_level"] == "HIGH"
    assert first_segment["limited_data"] is False
    assert first_segment["edge_id"] == "short_1"
    assert first_segment["crowd_score"] == 200.0
    assert first_segment["crowd_score_unit"] == "pedestrians_per_minute"
    assert first_segment["routing_penalty"] is None
    assert first_segment["congestion_level"] == "HIGH"
    assert first_segment["crowd_source"] == "historical_pattern"
    assert first_segment["coverage_status"] == "HISTORICAL_PATTERN"
    assert first_segment["evaluated_at"] is None
    assert first_segment["observed_at"] is None
    assert first_segment["geometry"]["coordinates"][0] == [144.963, -37.813]


def test_only_api_v1_route_is_exposed() -> None:
    client, _ = api_client()

    assert client.post("/api/v1/routes/compare", json=route_request()).status_code == 200
    assert client.post("/routes/compare", json=route_request()).status_code == 404
    production_paths = {route.path for route in production_app.routes}
    assert "/api/v1/routes/compare" in production_paths
    assert "/routes/compare" not in production_paths


def test_current_request_refreshes_live_contexts() -> None:
    client, repository = api_client()
    for edge_id, score, observed_at in (
        ("short_1", 80, "2026-08-10T02:30:00Z"),
        ("short_2", 80, "2026-08-10T02:31:00Z"),
        ("quiet_1", 5, "2026-08-10T02:32:00Z"),
        ("quiet_2", 5, "2026-08-10T02:32:00Z"),
    ):
        repository.contexts[edge_id] = CurrentContext(
            crowd_count=score,
            crowd_level=None,
            sensory_indicator=None,
            observation_status="CURRENT",
            coverage_status="OBSERVED",
            as_of="2026-08-10T02:38:00Z",
            source_observed_at=observed_at,
            sensor_count=1,
            aggregation_method="maximum",
        )
    response = client.post("/api/v1/routes/compare", json=route_request(travel_time=None))

    assert response.status_code == 200
    body = response.json()
    assert body["current_data_used"] is True
    assert body["data_as_of"] == "2026-08-10T02:32:00Z"
    assert body["shortest_route"]["segments"][0]["observed_at"] == "2026-08-10T02:30:00Z"
    assert repository.refresh_count == 1


def test_live_window_without_live_observations_reports_current_data_not_used() -> None:
    client, repository = api_client()

    response = client.post("/api/v1/routes/compare", json=route_request(travel_time=None))

    assert response.status_code == 200
    assert repository.refresh_count == 1
    assert response.json()["current_data_used"] is False
    assert response.json()["data_as_of"] is None


def test_edge_endpoint_exposes_real_observation_time_and_max_aggregation() -> None:
    client, repository = api_client()
    repository.contexts["quiet_1"] = CurrentContext(
        crowd_count=42,
        # An upstream level from an older rule must not override v1 thresholds.
        crowd_level="HIGH",
        sensory_indicator=None,
        observation_status="CURRENT",
        coverage_status="OBSERVED",
        as_of="2026-08-10T02:38:00Z",
        source_observed_at="2026-08-10T02:30:00Z",
        sensor_count=2,
        aggregation_method="maximum",
    )

    response = client.get("/api/v1/edges/quiet_1?weekday_index=0&local_hour=12")

    assert response.status_code == 200
    crowd = response.json()["crowd"]
    assert crowd["score"] == 42.0
    assert crowd["routing_penalty"] is None
    assert crowd["source"] == "current_observation"
    assert crowd["congestion_level"] == "LOW"
    assert crowd["evaluated_at"] == "2026-08-10T02:38:00Z"
    assert crowd["observed_at"] == "2026-08-10T02:30:00Z"
    assert crowd["sensor_count"] == 2
    assert crowd["aggregation_method"] == "maximum"

    historical = client.get(
        "/api/v1/edges/quiet_1?weekday_index=0&local_hour=12&use_current=false"
    ).json()["crowd"]
    assert historical["score"] == 10.0
    assert historical["score_unit"] == "pedestrians_per_minute"
    assert historical["source"] == "historical_pattern"
    assert historical["observed_at"] is None


def test_rds_refresh_query_uses_maximum_and_rejects_future_observations(monkeypatch) -> None:
    repository = RdsRepository(
        DatabaseSettings("unused", 3306, "unused", "unused", "unused", None, 1)
    )

    class FakeCursor:
        query = ""

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def execute(self, query):
            self.query = query

        def fetchall(self):
            return [
                {
                    "edge_id": "edge_live",
                    "source_observed_at": "2026-08-10T02:30:00Z",
                    "newest_age_seconds": 60,
                    "current_sensor_count": 2,
                    "current_crowd_count": 100,
                }
            ]

    cursor = FakeCursor()

    class FakeConnection:
        def cursor(self):
            return cursor

    @contextmanager
    def fake_connection():
        yield FakeConnection()

    monkeypatch.setattr(repository, "_connection", fake_connection)
    repository.refresh_current_contexts()

    assert "MAX(count_total) AS current_crowd_count" in cursor.query
    assert "AVG(" not in cursor.query
    assert "WHERE observed_at_utc <= UTC_TIMESTAMP()" in cursor.query
    assert "sensor.count_total = statistics.current_crowd_count" in cursor.query
    assert repository.contexts["edge_live"].crowd_count == 100.0
    assert repository.contexts["edge_live"].sensor_count == 2
    assert repository.contexts["edge_live"].aggregation_method == "maximum"


def test_unknown_edge_separates_display_score_from_routing_penalty() -> None:
    client, _ = api_client()
    response = client.get("/api/v1/edges/short_1?weekday_index=1&local_hour=1")

    assert response.status_code == 200
    crowd = response.json()["crowd"]
    assert crowd["score"] is None
    assert crowd["routing_penalty"] == 75.0
    assert crowd["source"] == "unknown"
    assert crowd["congestion_level"] == "UNKNOWN"


def test_exposure_and_coverage_are_weighted_by_distance() -> None:
    repository = FakeRepository()
    repository.edges["short_1"] = repository._edge("short_1", "origin", "short_mid", 100, 10)
    repository.edges["short_2"] = repository._edge("short_2", "short_mid", "destination", 900, 10)
    repository.patterns.pop(("short_2", 0, 12))
    service = RoutingService(repository)

    summary = service.route_summary(
        PathResult(repository.adjacency["origin"][:1] + repository.adjacency["short_mid"]),
        "shortest",
        weekday_index=0,
        local_hour=12,
        use_current=False,
    )

    assert summary["crowd_exposure"] == 200.0
    assert summary["known_distance_m"] == 100.0
    assert summary["total_distance_m"] == 1000.0
    assert summary["data_coverage_ratio"] == 0.1
    assert summary["segments"][1]["crowd_score"] is None
    assert summary["segments"][1]["routing_penalty"] == 75.0


def test_reverse_arc_reverses_segment_geojson_coordinates() -> None:
    repository = FakeRepository()
    service = RoutingService(repository)
    reverse_arc = Arc("short_1", "origin", 10, traverses_reverse=True)

    summary = service.route_summary(
        PathResult([reverse_arc]),
        "shortest",
        weekday_index=0,
        local_hour=12,
        use_current=False,
    )

    assert summary["segments"][0]["geometry"]["coordinates"] == [
        [144.958, -37.816],
        [144.963, -37.813],
    ]
    assert summary["geometry"]["coordinates"] == [
        [144.958, -37.816],
        [144.963, -37.813],
    ]


def test_splitting_same_distance_does_not_change_crowd_metrics() -> None:
    split_repository = FakeRepository()
    split_service = RoutingService(split_repository)
    split_summary = split_service.route_summary(
        PathResult(
            split_repository.adjacency["origin"][:1]
            + split_repository.adjacency["short_mid"]
        ),
        "shortest",
        weekday_index=0,
        local_hour=12,
        use_current=False,
    )

    single_repository = FakeRepository()
    single_repository.edges["short_1"] = single_repository._edge(
        "short_1", "origin", "short_mid", 1000, 20
    )
    single_service = RoutingService(single_repository)
    single_summary = single_service.route_summary(
        PathResult([Arc("short_1", "short_mid", 20)]),
        "shortest",
        weekday_index=0,
        local_hour=12,
        use_current=False,
    )

    assert split_summary["crowd_exposure"] == single_summary["crowd_exposure"] == 200.0
    assert split_summary["routing_crowd_cost"] == single_summary["routing_crowd_cost"] == 200.0
    assert split_summary["data_coverage_ratio"] == single_summary["data_coverage_ratio"] == 1.0


def test_same_route_returns_structured_shortest_already_best_status() -> None:
    client, repository = api_client()
    for key in list(repository.patterns):
        repository.patterns[key] = HistoricalPattern(5, 5, 0, 10)

    response = client.post("/api/v1/routes/compare", json=route_request())

    assert response.status_code == 200
    body = response.json()
    assert body["recommendation_status"] == "SHORTEST_ALREADY_BEST"
    assert body["recommended_route_is_distinct"] is False
    assert body["crowd_exposure_reduction_percent"] is None
    assert body["recommended_route"]["route_type"] == "shortest"


def test_distinct_candidate_without_lower_exposure_is_not_recommended(monkeypatch) -> None:
    client, repository = api_client()
    for key in list(repository.patterns):
        repository.patterns[key] = HistoricalPattern(5, 5, 0, 10)

    paths = iter(
        [
            PathResult(repository.adjacency["origin"][:1] + repository.adjacency["short_mid"]),
            PathResult(repository.adjacency["origin"][1:] + repository.adjacency["quiet_mid"]),
        ]
    )
    monkeypatch.setattr(
        client.app.state.routing_service,
        "shortest_path",
        lambda *_args, **_kwargs: next(paths),
    )

    response = client.post("/api/v1/routes/compare", json=route_request())

    assert response.status_code == 200
    body = response.json()
    assert body["recommendation_status"] == "NO_ALTERNATIVE"
    assert body["recommended_route_is_distinct"] is True
    assert body["recommended_route"]["route_type"] == "sensory_candidate"
    assert body["crowd_exposure_reduction_percent"] is None


def test_all_unknown_data_returns_insufficient_status_and_null_exposure() -> None:
    client, repository = api_client()
    repository.patterns.clear()

    response = client.post("/api/v1/routes/compare", json=route_request())

    assert response.status_code == 200
    body = response.json()
    assert body["recommendation_status"] == "INSUFFICIENT_DATA"
    assert body["shortest_route"]["crowd_exposure"] is None
    assert body["shortest_route"]["data_coverage_ratio"] == 0.0
    assert body["shortest_route"]["limited_data"] is True
    assert body["shortest_route"]["crowd_level"] is None
    assert body["shortest_route"]["sensory_level"] is None
    assert all(segment["crowd_score"] is None for segment in body["shortest_route"]["segments"])


def test_coverage_just_below_sixty_percent_stays_insufficient() -> None:
    client, repository = api_client()
    repository.edges["short_1"] = repository._edge(
        "short_1", "origin", "short_mid", 599.96, 10
    )
    repository.edges["short_2"] = repository._edge(
        "short_2", "short_mid", "destination", 400.04, 10
    )
    repository.patterns.pop(("short_2", 0, 12))

    response = client.post("/api/v1/routes/compare", json=route_request())

    assert response.status_code == 200
    body = response.json()
    assert body["shortest_route"]["data_coverage_ratio"] == 0.59996
    assert body["recommendation_status"] == "INSUFFICIENT_DATA"
    assert body["warning"].startswith("Limited crowd data")
    assert "High pedestrian congestion" in body["warning"]


def test_exactly_sixty_percent_coverage_is_not_limited() -> None:
    repository = FakeRepository()
    repository.edges["short_1"] = repository._edge(
        "short_1", "origin", "short_mid", 600, 10
    )
    repository.edges["short_2"] = repository._edge(
        "short_2", "short_mid", "destination", 400, 10
    )
    repository.patterns.pop(("short_2", 0, 12))

    summary = RoutingService(repository).route_summary(
        PathResult(repository.adjacency["origin"][:1] + repository.adjacency["short_mid"]),
        "shortest",
        weekday_index=0,
        local_hour=12,
        use_current=False,
    )

    assert summary["data_coverage_ratio"] == 0.6
    assert summary["limited_data"] is False
    assert summary["crowd_level"] == "HIGH"
    assert summary["unknown_distance_m"] == 400.0


def test_historical_hourly_count_is_converted_to_per_minute_before_classification() -> None:
    repository = FakeRepository()
    repository.patterns[("short_1", 0, 12)] = HistoricalPattern(3000, 5, 2400, 3600)

    crowd = RoutingService(repository).crowd_for_edge(
        "short_1", weekday_index=0, local_hour=12, use_current=False
    )

    assert crowd.score == 50.0
    assert crowd.level == "LOW"


def test_crowd_threshold_boundaries_are_inclusive() -> None:
    assert congestion_level(50.0) == "LOW"
    assert congestion_level(50.0001) == "MEDIUM"
    assert congestion_level(150.0) == "MEDIUM"
    assert congestion_level(150.0001) == "HIGH"


def test_invalid_coordinates_are_rejected() -> None:
    client, _ = api_client()
    payload = route_request()
    payload["origin"]["latitude"] = 91

    assert client.post("/api/v1/routes/compare", json=payload).status_code == 422


def test_locations_resolving_to_same_node_are_rejected() -> None:
    client, _ = api_client()
    payload = route_request()
    payload["destination"] = payload["origin"].copy()

    response = client.post("/api/v1/routes/compare", json=payload)

    assert response.status_code == 422
    assert response.json()["detail"] == "Origin and destination resolve to the same routing node."


def test_cors_origins_can_be_replaced_by_environment(monkeypatch) -> None:
    monkeypatch.setenv(
        "CORS_ALLOWED_ORIGINS",
        " https://frontend.example.com, http://localhost:4173, ",
    )

    assert cors_allowed_origins() == [
        "https://frontend.example.com",
        "http://localhost:4173",
    ]


def test_production_cors_preflight_allows_deployed_frontend_only() -> None:
    client = TestClient(production_app)
    allowed = client.options(
        "/api/v1/routes/compare",
        headers={
            "Origin": "https://dpevp4238kw5k.cloudfront.net",
            "Access-Control-Request-Method": "POST",
        },
    )
    blocked = client.options(
        "/api/v1/routes/compare",
        headers={
            "Origin": "https://not-configured.example.com",
            "Access-Control-Request-Method": "POST",
        },
    )

    assert allowed.status_code == 200
    assert allowed.headers["access-control-allow-origin"] == "https://dpevp4238kw5k.cloudfront.net"
    assert "access-control-allow-origin" not in blocked.headers


def test_netlify_json_post_preflight_is_allowed_without_credentials() -> None:
    client = TestClient(production_app)
    response = client.options(
        "/api/v1/routes/compare",
        headers={
            "Origin": "https://calmpath-tp10.netlify.app",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    delete_response = client.options(
        "/api/v1/routes/compare",
        headers={
            "Origin": "https://calmpath-tp10.netlify.app",
            "Access-Control-Request-Method": "DELETE",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "https://calmpath-tp10.netlify.app"
    assert "POST" in response.headers["access-control-allow-methods"]
    assert "content-type" in response.headers["access-control-allow-headers"].lower()
    assert "access-control-allow-credentials" not in response.headers
    assert delete_response.status_code == 400
