import pytest
from fastapi.testclient import TestClient

from app.api.routes import refuges as refuge_routes
from app.main import app
from app.services.address_service import AddressService


client = TestClient(app)


MATCHED_ROW = {
    "latitude": -37.795,
    "longitude": 144.958,
    "address": "61 Royal Parade Parkville",
    "address_latitude": -37.79516121,
    "address_longitude": 144.95776822,
    "address_distance_m": 42.5,
    "address_source": "Shogo address matching",
    "address_match_status": "MATCHED",
}


class FakeDatabaseClient:
    def __init__(self, rows: list[dict[str, object]]) -> None:
        self.rows = rows
        self.calls: list[tuple[str, tuple[object, ...]]] = []

    def fetch_all(self, query: str, params: tuple[object, ...] = ()) -> list[dict[str, object]]:
        self.calls.append((query, params))
        return [
            row
            for row in self.rows
            if row["latitude"] == params[0]
            and row["longitude"] == params[1]
            and row["address_match_status"] == "MATCHED"
        ]


@pytest.fixture()
def install_address_service(monkeypatch: pytest.MonkeyPatch):
    def install(rows: list[dict[str, object]]) -> FakeDatabaseClient:
        database_client = FakeDatabaseClient(rows)
        monkeypatch.setattr(refuge_routes, "address_service", AddressService(database_client))
        return database_client

    return install


def test_address_returns_database_fields_and_uses_coordinates(install_address_service) -> None:
    database_client = install_address_service([MATCHED_ROW])

    response = client.get(
        "/api/v1/refuges/address",
        params={"latitude": -37.795, "longitude": 144.958},
    )

    assert response.status_code == 200
    assert response.json() == {
        "address": "61 Royal Parade Parkville",
        "latitude": -37.79516121,
        "longitude": 144.95776822,
        "match_distance_m": 42.5,
        "source": "Shogo address matching",
    }
    assert len(database_client.calls) == 1
    query, params = database_client.calls[0]
    assert "backend_refuge_candidates" in query
    assert "address_match_status = 'MATCHED'" in query
    assert params == (-37.795, 144.958)


def test_address_ignores_unmatched_database_rows(install_address_service) -> None:
    unmatched_row = {**MATCHED_ROW, "address": "Unmatched address", "address_match_status": "UNMATCHED"}
    database_client = install_address_service([unmatched_row])

    response = client.get(
        "/api/v1/refuges/address",
        params={"latitude": -37.795, "longitude": 144.958},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "No matched address found for the selected refuge"
    assert len(database_client.calls) == 1


def test_address_returns_404_when_no_database_row_matches_coordinates(install_address_service) -> None:
    database_client = install_address_service([MATCHED_ROW])

    response = client.get(
        "/api/v1/refuges/address",
        params={"latitude": -37.7, "longitude": 144.9},
    )

    assert response.status_code == 404
    assert len(database_client.calls) == 1


@pytest.mark.parametrize(
    "params",
    [
        {"latitude": "nan", "longitude": 144.958},
        {"latitude": -91, "longitude": 144.958},
        {"latitude": -37.795, "longitude": "nan"},
        {"latitude": -37.795, "longitude": 181},
    ],
)
def test_address_invalid_coordinates_return_422(install_address_service, params) -> None:
    database_client = install_address_service([])

    response = client.get("/api/v1/refuges/address", params=params)

    assert response.status_code == 422
    assert database_client.calls == []
