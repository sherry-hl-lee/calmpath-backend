from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.routes import refuges as refuge_routes
from app.main import app
from app.services.refuge_service import RefugeService


client = TestClient(app)
CSV_CONTENT = """landmark_id,feature_name,sub_theme,latitude,longitude,is_refuge_candidate
refuge-001,Willow Quiet Park,Informal Outdoor Facility (Park/Garden/Reserve),-37.8136,144.9631,true
refuge-002,Lantern Reading Library,Library,-37.806,144.9631,true
refuge-003,Excluded Candidate,Library,-37.8137,144.9631,false
refuge-004,Unsupported Candidate,Community Facility,-37.81365,144.9631,true
"""


@pytest.fixture()
def configured_refuge_service(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    csv_path = tmp_path / "refuge_candidates.csv"
    csv_path.write_text(CSV_CONTENT, encoding="utf-8")
    monkeypatch.setattr(refuge_routes, "refuge_service", RefugeService(csv_path))


def test_nearby_refuges_returns_200(configured_refuge_service: None) -> None:
    response = client.get(
        "/api/v1/refuges/nearby",
        params={"latitude": -37.8136, "longitude": 144.9631, "radius_m": 5000},
    )

    assert response.status_code == 200


def test_nearby_refuges_has_new_contract_and_type_mapping(
    configured_refuge_service: None,
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


def test_nearby_refuges_are_sorted_by_distance(configured_refuge_service: None) -> None:
    response = client.get(
        "/api/v1/refuges/nearby",
        params={"latitude": -37.8136, "longitude": 144.9631, "radius_m": 5000},
    )

    distances = [refuge["distance_m"] for refuge in response.json()]

    assert distances == sorted(distances)


def test_refuges_outside_radius_are_not_returned(configured_refuge_service: None) -> None:
    response = client.get(
        "/api/v1/refuges/nearby",
        params={"latitude": -37.8136, "longitude": 144.9631, "radius_m": 100},
    )

    assert response.status_code == 200
    assert [refuge["id"] for refuge in response.json()] == ["refuge-001"]


def test_non_candidates_are_not_returned(configured_refuge_service: None) -> None:
    response = client.get(
        "/api/v1/refuges/nearby",
        params={"latitude": -37.8136, "longitude": 144.9631, "radius_m": 100},
    )

    assert "refuge-003" not in [refuge["id"] for refuge in response.json()]


def test_nearby_refuge_parameters_return_422(configured_refuge_service: None) -> None:
    invalid_requests = [
        {"latitude": -91, "longitude": 144.9631, "radius_m": 1000},
        {"latitude": -37.8136, "longitude": 181, "radius_m": 1000},
        {"latitude": -37.8136, "longitude": 144.9631, "radius_m": 0},
    ]

    for params in invalid_requests:
        response = client.get("/api/v1/refuges/nearby", params=params)

        assert response.status_code == 422


def test_nearby_endpoint_does_not_call_address_service(
    configured_refuge_service: None,
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
