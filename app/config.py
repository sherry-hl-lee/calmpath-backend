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
        missing = [name for name in ("MYSQL_HOST", "MYSQL_USER", "MYSQL_PASSWORD") if not os.getenv(name)]
        if missing:
            raise RuntimeError(
                "Missing required RDS configuration: " + ", ".join(missing) + ". "
                "Set these environment variables or load them from AWS Secrets Manager."
            )
        return cls(
            host=os.environ["MYSQL_HOST"],
            port=int(os.getenv("MYSQL_PORT", "3306")),
            database=os.getenv("MYSQL_DATABASE", "fit5120_data"),
            user=os.environ["MYSQL_USER"],
            password=os.environ["MYSQL_PASSWORD"],
            ssl_ca=os.getenv("MYSQL_SSL_CA") or None,
            connect_timeout_seconds=int(os.getenv("MYSQL_CONNECT_TIMEOUT_SECONDS", "10")),
        )
