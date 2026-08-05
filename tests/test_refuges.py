from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_nearby_refuges_returns_200() -> None:
    response = client.get(
        "/api/v1/refuges/nearby",
        params={"latitude": -37.8136, "longitude": 144.9631, "radius_m": 5000},
    )

    assert response.status_code == 200


def test_nearby_refuges_contains_required_fields() -> None:
    response = client.get(
        "/api/v1/refuges/nearby",
        params={"latitude": -37.8136, "longitude": 144.9631, "radius_m": 5000},
    )

    required_fields = {
        "id",
        "name",
        "type",
        "distance_m",
        "latitude",
        "longitude",
        "address",
    }
    results = response.json()

    assert results
    assert all(required_fields <= set(refuge) for refuge in results)


def test_nearby_refuges_are_sorted_by_distance() -> None:
    response = client.get(
        "/api/v1/refuges/nearby",
        params={"latitude": -37.8136, "longitude": 144.9631, "radius_m": 5000},
    )

    distances = [refuge["distance_m"] for refuge in response.json()]

    assert distances == sorted(distances)


def test_refuges_outside_radius_are_not_returned() -> None:
    response = client.get(
        "/api/v1/refuges/nearby",
        params={"latitude": -37.8136, "longitude": 144.9631, "radius_m": 100},
    )

    results = response.json()

    assert response.status_code == 200
    assert [refuge["id"] for refuge in results] == ["refuge-001"]


def test_invalid_nearby_refuge_parameters_return_422() -> None:
    invalid_requests = [
        {"latitude": -91, "longitude": 144.9631, "radius_m": 1000},
        {"latitude": -37.8136, "longitude": 181, "radius_m": 1000},
        {"latitude": -37.8136, "longitude": 144.9631, "radius_m": 0},
    ]

    for params in invalid_requests:
        response = client.get("/api/v1/refuges/nearby", params=params)

        assert response.status_code == 422
