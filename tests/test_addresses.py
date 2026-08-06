import httpx
import pytest
from fastapi.testclient import TestClient

from app.api.routes import refuges as refuge_routes
from app.main import app
from app.services.address_service import AddressService


client = TestClient(app)


@pytest.fixture()
def install_address_service(monkeypatch: pytest.MonkeyPatch):
    def install(handler):
        http_client = httpx.Client(transport=httpx.MockTransport(handler), timeout=5)
        service = AddressService(client=http_client)
        monkeypatch.setattr(refuge_routes, "address_service", service)
        return service

    return install


def test_address_returns_nearest_address_and_uses_encoded_query(install_address_service) -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json={
                "total_count": 1,
                "results": [
                    {
                        "address_pnt": "61 Royal Parade Parkville",
                        "latitude": -37.79516121,
                        "longitude": 144.95776822,
                        "match_distance_m": 42.5,
                    }
                ]
            },
            request=request,
        )

    install_address_service(handler)
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
        "source": "City of Melbourne Street Addresses",
    }
    assert requests[0].url.host == "data.melbourne.vic.gov.au"
    assert "within_distance" in requests[0].url.params["where"]
    assert "POINT(144.958 -37.795)" in requests[0].url.params["where"]
    assert requests[0].url.params["limit"] == "1"


@pytest.mark.parametrize(
    "payload",
    [
        {"total_count": 0, "results": []},
        {"total_count": 1, "results": [{"address_pnt": ""}]},
    ],
)
def test_address_returns_404_when_no_valid_nearby_address(
    install_address_service,
    payload: dict[str, object],
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload, request=request)

    install_address_service(handler)
    response = client.get(
        "/api/v1/refuges/address",
        params={"latitude": -37.795, "longitude": 144.958},
    )

    assert response.status_code == 404
    assert "200 metres" in response.json()["detail"]


def test_address_upstream_429_maps_to_503_without_retry(install_address_service) -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(429, headers={"Retry-After": "17"}, request=request)

    install_address_service(handler)
    response = client.get(
        "/api/v1/refuges/address",
        params={"latitude": -37.795, "longitude": 144.958},
    )

    assert response.status_code == 503
    assert response.headers["Retry-After"] == "17"
    assert calls == 1


def test_address_upstream_500_maps_to_503(install_address_service) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, request=request)

    install_address_service(handler)
    response = client.get(
        "/api/v1/refuges/address",
        params={"latitude": -37.795, "longitude": 144.958},
    )

    assert response.status_code == 503
    assert "server error" in response.json()["detail"]


def test_address_timeout_maps_to_503(install_address_service) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out", request=request)

    install_address_service(handler)
    response = client.get(
        "/api/v1/refuges/address",
        params={"latitude": -37.795, "longitude": 144.958},
    )

    assert response.status_code == 503
    assert "timed out" in response.json()["detail"]


def test_address_invalid_json_maps_to_503(install_address_service) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=b"not-json",
            headers={"Content-Type": "application/json"},
            request=request,
        )

    install_address_service(handler)
    response = client.get(
        "/api/v1/refuges/address",
        params={"latitude": -37.795, "longitude": 144.958},
    )

    assert response.status_code == 503
    assert "invalid JSON" in response.json()["detail"]


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
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("invalid coordinates must not call upstream")

    install_address_service(handler)
    response = client.get("/api/v1/refuges/address", params=params)

    assert response.status_code == 422


def test_address_ip_rate_limit_returns_429_with_retry_after(install_address_service) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"total_count": 0, "results": []}, request=request)

    install_address_service(handler)
    for index in range(30):
        response = client.get(
            "/api/v1/refuges/address",
            params={"latitude": -37.7 + index / 10000, "longitude": 144.9},
        )
        assert response.status_code == 404

    response = client.get(
        "/api/v1/refuges/address",
        params={"latitude": -37.6, "longitude": 144.9},
    )

    assert response.status_code == 429
    assert int(response.headers["Retry-After"]) >= 1


def test_address_cache_avoids_duplicate_upstream_request(install_address_service) -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(
            200,
            json={
                "total_count": 1,
                "results": [
                    {
                        "address_pnt": "61 Royal Parade Parkville",
                        "latitude": -37.79516121,
                        "longitude": 144.95776822,
                        "match_distance_m": 42.5,
                    }
                ]
            },
            request=request,
        )

    install_address_service(handler)
    first = client.get(
        "/api/v1/refuges/address",
        params={"latitude": -37.795, "longitude": 144.958},
    )
    second = client.get(
        "/api/v1/refuges/address",
        params={"latitude": -37.795004, "longitude": 144.958004},
    )

    assert first.status_code == second.status_code == 200
    assert first.json() == second.json()
    assert calls == 1
