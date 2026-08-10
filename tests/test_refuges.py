import pytest
from fastapi.testclient import TestClient

from app.api.routes import refuges as refuge_routes
from app.main import app
from app.services.refuge_service import RefugeService


client = TestClient(app)

RDS_ROWS = [
    {
        "landmark_id": "refuge-001",
        "feature_name": "Willow Quiet Park",
        "sub_theme": "Informal Outdoor Facility (Park/Garden/Reserve)",
        "latitude": -37.8136,
        "longitude": 144.9631,
        "is_refuge_candidate": 1,
    },
    {
        "landmark_id": "refuge-002",
        "feature_name": "Lantern Reading Library",
        "sub_theme": "Library",
        "latitude": -37.806,
        "longitude": 144.9631,
        "is_refuge_candidate": 1,
    },
    {
        "landmark_id": "refuge-003",
        "feature_name": "Excluded Candidate",
        "sub_theme": "Library",
        "latitude": -37.8137,
        "longitude": 144.9631,
        "is_refuge_candidate": 0,
    },
    {
        "landmark_id": "refuge-004",
        "feature_name": "Unsupported Candidate",
        "sub_theme": "Community Facility",
        "latitude": -37.81365,
        "longitude": 144.9631,
        "is_refuge_candidate": 1,
    },
]


class FakeDatabaseClient:
    def __init__(self, rows: list[dict[str, object]]) -> None:
        self.rows = rows
        self.calls: list[tuple[str, tuple[object, ...]]] = []

    def fetch_all(self, query: str, params: tuple[object, ...] = ()) -> list[dict[str, object]]:
        self.calls.append((query, params))
        return [row for row in self.rows if row["is_refuge_candidate"] == 1]


@pytest.fixture()
def configured_refuge_service(monkeypatch: pytest.MonkeyPatch) -> FakeDatabaseClient:
    database_client = FakeDatabaseClient(RDS_ROWS)
    monkeypatch.setattr(refuge_routes, "refuge_service", RefugeService(database_client))
    return database_client


def test_nearby_refuges_returns_200(configured_refuge_service: FakeDatabaseClient) -> None:
    response = client.get(
        "/api/v1/refuges/nearby",
        params={"latitude": -37.8136, "longitude": 144.9631, "radius_m": 5000},
    )

    assert response.status_code == 200


def test_nearby_refuges_has_new_contract_and_type_mapping(
    configured_refuge_service: FakeDatabaseClient,
) -> None:
    response = client.get(
        "/api/v1/refuges/nearby",
        params={"latitude": -37.8136, "longitude": 144.9631, "radius_m": 5000},
    )

    required_fields = {"id", "name", "type", "latitude", "longitude", "distance_m"}
    results = response.json()

    assert results
    assert all(set(refuge) == required_fields for refuge in results)
    assert {refuge["type"] for refuge in results} == {"park", "library"}


def test_nearby_refuges_are_sorted_by_distance(configured_refuge_service: FakeDatabaseClient) -> None:
    response = client.get(
        "/api/v1/refuges/nearby",
        params={"latitude": -37.8136, "longitude": 144.9631, "radius_m": 5000},
    )

    distances = [refuge["distance_m"] for refuge in response.json()]

    assert distances == sorted(distances)


def test_refuges_outside_radius_are_not_returned(configured_refuge_service: FakeDatabaseClient) -> None:
    response = client.get(
        "/api/v1/refuges/nearby",
        params={"latitude": -37.8136, "longitude": 144.9631, "radius_m": 100},
    )

    assert response.status_code == 200
    assert [refuge["id"] for refuge in response.json()] == ["refuge-001"]


def test_non_candidates_are_not_returned(configured_refuge_service: FakeDatabaseClient) -> None:
    response = client.get(
        "/api/v1/refuges/nearby",
        params={"latitude": -37.8136, "longitude": 144.9631, "radius_m": 100},
    )

    assert "refuge-003" not in [refuge["id"] for refuge in response.json()]


def test_nearby_refuge_parameters_return_422(configured_refuge_service: FakeDatabaseClient) -> None:
    invalid_requests = [
        {"latitude": -91, "longitude": 144.9631, "radius_m": 1000},
        {"latitude": -37.8136, "longitude": 181, "radius_m": 1000},
        {"latitude": -37.8136, "longitude": 144.9631, "radius_m": 0},
    ]

    for params in invalid_requests:
        response = client.get("/api/v1/refuges/nearby", params=params)

        assert response.status_code == 422


def test_nearby_endpoint_does_not_call_address_service(
    configured_refuge_service: FakeDatabaseClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class UnexpectedAddressCall:
        def find_address(self, *args: object) -> None:
            raise AssertionError("nearby must not call the address service")

    monkeypatch.setattr(refuge_routes, "address_service", UnexpectedAddressCall())

    response = client.get(
        "/api/v1/refuges/nearby",
        params={"latitude": -37.8136, "longitude": 144.9631, "radius_m": 100},
    )

    assert response.status_code == 200


def test_nearby_query_uses_rds_candidate_filter(
    configured_refuge_service: FakeDatabaseClient,
) -> None:
    response = client.get(
        "/api/v1/refuges/nearby",
        params={"latitude": -37.8136, "longitude": 144.9631, "radius_m": 5000},
    )

    assert response.status_code == 200
    assert len(configured_refuge_service.calls) == 1
    query, params = configured_refuge_service.calls[0]
    assert "backend_refuge_candidates" in query
    assert "is_refuge_candidate = 1" in query
    assert params == ()
