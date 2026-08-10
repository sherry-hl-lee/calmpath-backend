from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.config import DatabaseSettings, data_source_from_environment
from app.main import app, create_repository
from app.services.fake_repository import FakeRepository


RDS_VARIABLES = (
    "RDS_HOST",
    "RDS_PORT",
    "RDS_DATABASE",
    "RDS_USER",
    "RDS_PASSWORD",
)


def clear_rds_environment(monkeypatch) -> None:
    for name in RDS_VARIABLES:
        monkeypatch.delenv(name, raising=False)


def test_data_source_must_be_explicit_and_supported(monkeypatch) -> None:
    monkeypatch.delenv("DATA_SOURCE", raising=False)
    with pytest.raises(RuntimeError, match="Unsupported DATA_SOURCE"):
        data_source_from_environment()

    monkeypatch.setenv("DATA_SOURCE", "csv")
    with pytest.raises(RuntimeError, match="Unsupported DATA_SOURCE"):
        data_source_from_environment()


def test_database_settings_use_only_rds_variable_names(monkeypatch) -> None:
    clear_rds_environment(monkeypatch)
    monkeypatch.setenv("MYSQL_HOST", "legacy-host")
    monkeypatch.setenv("MYSQL_USER", "legacy-user")
    monkeypatch.setenv("MYSQL_PASSWORD", "legacy-password")
    with pytest.raises(RuntimeError, match="RDS_HOST"):
        DatabaseSettings.from_environment()

    values = {
        "RDS_HOST": "database.internal",
        "RDS_PORT": "3307",
        "RDS_DATABASE": "fit5120_data",
        "RDS_USER": "fit5120_app",
        "RDS_PASSWORD": "test-secret",
    }
    for name, value in values.items():
        monkeypatch.setenv(name, value)
    settings = DatabaseSettings.from_environment()
    assert settings.host == "database.internal"
    assert settings.port == 3307
    assert settings.database == "fit5120_data"
    assert settings.user == "fit5120_app"
    assert settings.password == "test-secret"


@pytest.mark.parametrize("missing_name", RDS_VARIABLES)
def test_every_required_rds_variable_is_validated(monkeypatch, missing_name) -> None:
    values = {
        "RDS_HOST": "database.internal",
        "RDS_PORT": "3306",
        "RDS_DATABASE": "fit5120_data",
        "RDS_USER": "fit5120_app",
        "RDS_PASSWORD": "test-secret",
    }
    for name, value in values.items():
        monkeypatch.setenv(name, value)
    monkeypatch.delenv(missing_name)

    with pytest.raises(RuntimeError, match=missing_name):
        DatabaseSettings.from_environment()


def test_fake_repository_mode_never_connects_to_mysql(monkeypatch) -> None:
    monkeypatch.setenv("DATA_SOURCE", "fake")
    clear_rds_environment(monkeypatch)

    def fail_if_called(*args, **kwargs):
        raise AssertionError("Fake mode must not connect to MySQL")

    monkeypatch.setattr("app.services.data_service.pymysql.connect", fail_if_called)
    repository = create_repository()
    assert isinstance(repository, FakeRepository)
    assert repository.nodes
    assert repository.edges


def test_fake_application_supports_health_edge_and_route_endpoints(monkeypatch) -> None:
    monkeypatch.setenv("DATA_SOURCE", "fake")
    clear_rds_environment(monkeypatch)

    with TestClient(app) as client:
        health = client.get("/api/v1/health")
        edge = client.get("/api/v1/edges/short_1")
        route = client.post(
            "/api/v1/routes/compare",
            json={
                "origin": {"latitude": -37.813, "longitude": 144.963},
                "destination": {"latitude": -37.820, "longitude": 144.950},
                "travel_time": None,
            },
        )
        reverse = client.post(
            "/api/v1/routes/compare",
            json={
                "origin": {"latitude": -37.820, "longitude": 144.950},
                "destination": {"latitude": -37.813, "longitude": 144.963},
                "travel_time": None,
            },
        )

    assert health.status_code == 200
    assert health.json()["nodes"] == 4
    assert edge.status_code == 200
    assert edge.json()["edge_id"] == "short_1"
    assert route.status_code == 200
    body = route.json()
    assert body["recommendation_status"] == "LOWER_CROWD"
    assert body["current_data_used"] is False
    assert body["data_as_of"] is None
    assert all(
        segment["crowd_source"] == "historical_pattern"
        and segment["observed_at"] is None
        for summary in (body["shortest_route"], body["recommended_route"])
        for segment in summary["segments"]
    )
    assert body["recommended_route"]["crowd_exposure"] < body["shortest_route"]["crowd_exposure"]

    assert reverse.status_code == 200
    assert reverse.json()["recommendation_status"] == "LOWER_CROWD"


def test_rds_mode_never_falls_back_to_fake_when_configuration_is_missing(monkeypatch) -> None:
    monkeypatch.setenv("DATA_SOURCE", "rds")
    clear_rds_environment(monkeypatch)

    def fail_if_called():
        raise AssertionError("RDS mode must not instantiate FakeRepository")

    monkeypatch.setattr("app.main.FakeRepository", fail_if_called)
    with pytest.raises(RuntimeError, match="Missing required RDS configuration"):
        create_repository()


def test_rds_mode_builds_rds_repository_only(monkeypatch) -> None:
    monkeypatch.setenv("DATA_SOURCE", "rds")
    settings = DatabaseSettings(
        host="database.internal",
        port=3306,
        database="fit5120_data",
        user="fit5120_app",
        password="test-secret",
        ssl_ca=None,
        connect_timeout_seconds=10,
    )
    monkeypatch.setattr(
        "app.main.DatabaseSettings.from_environment", classmethod(lambda cls: settings)
    )
    calls = {"load": 0}

    class StubRdsRepository:
        def __init__(self, received_settings):
            assert received_settings is settings

        def load(self):
            calls["load"] += 1

    monkeypatch.setattr("app.main.RdsRepository", StubRdsRepository)
    repository = create_repository()
    assert isinstance(repository, StubRdsRepository)
    assert calls["load"] == 1
