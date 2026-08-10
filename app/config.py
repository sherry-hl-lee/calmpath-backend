from __future__ import annotations

from dataclasses import dataclass
import os


MELBOURNE_TIMEZONE = "Australia/Melbourne"

# Prototype values only. They must be calibrated before a production release.
UNKNOWN_CROWD_PENALTY = 75.0
CROWD_WEIGHT_SECONDS = 1.0
HISTORICAL_COUNT_INTERVAL_MINUTES = 60.0
CROWD_SCORE_UNIT = "pedestrians_per_minute"
CROWD_LOW_MAX_PER_MINUTE = 50.0
CROWD_MEDIUM_MAX_PER_MINUTE = 150.0
CROWD_THRESHOLD_VERSION = "provisional-dmp-v1"
SENSORY_LEVEL_BASIS = "PEDESTRIAN_CROWD_ONLY"
LIVE_REQUEST_WINDOW_MINUTES = 15
MINIMUM_CROWD_COVERAGE_FOR_RECOMMENDATION = 0.60
SUPPORTED_DATA_SOURCES = {"fake", "rds"}


def data_source_from_environment() -> str:
    """Return the explicitly selected application repository mode."""

    value = os.getenv("DATA_SOURCE", "").strip().lower()
    if value not in SUPPORTED_DATA_SOURCES:
        supported = ", ".join(sorted(SUPPORTED_DATA_SOURCES))
        raise RuntimeError(
            f"Unsupported DATA_SOURCE {value!r}. Set DATA_SOURCE to one of: {supported}."
        )
    return value


def cors_allowed_origins() -> list[str]:
    """Return explicitly allowed frontend origins.

    A comma-separated environment variable keeps deployed frontend URLs out of
    application code while retaining useful local-development defaults.
    """

    default_origins = (
        "http://localhost:3000,http://127.0.0.1:3000,"
        "http://localhost:5173,http://127.0.0.1:5173,"
        "https://dpevp4238kw5k.cloudfront.net,"
        "https://calmpath-tp10.netlify.app"
    )
    return [
        origin.strip()
        for origin in os.getenv("CORS_ALLOWED_ORIGINS", default_origins).split(",")
        if origin.strip()
    ]


@dataclass(frozen=True)
class DatabaseSettings:
    """Read-only application connection settings supplied by the environment."""

    host: str
    port: int
    database: str
    user: str
    password: str
    ssl_ca: str | None
    connect_timeout_seconds: int

    @classmethod
    def from_environment(cls) -> "DatabaseSettings":
        required = (
            "RDS_HOST",
            "RDS_PORT",
            "RDS_DATABASE",
            "RDS_USER",
            "RDS_PASSWORD",
        )
        missing = [name for name in required if not os.getenv(name)]
        if missing:
            raise RuntimeError(
                "Missing required RDS configuration: " + ", ".join(missing) + ". "
                "Set these environment variables or load them from AWS Secrets Manager."
            )
        return cls(
            host=os.environ["RDS_HOST"],
            port=int(os.environ["RDS_PORT"]),
            database=os.environ["RDS_DATABASE"],
            user=os.environ["RDS_USER"],
            password=os.environ["RDS_PASSWORD"],
            ssl_ca=os.getenv("RDS_SSL_CA") or None,
            connect_timeout_seconds=int(os.getenv("RDS_CONNECT_TIMEOUT_SECONDS", "10")),
        )
