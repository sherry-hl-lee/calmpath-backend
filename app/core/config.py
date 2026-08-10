import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")

# Local development defaults to deterministic fake providers. The Docker image
# explicitly defaults to rds so a deployed container cannot silently serve fake
# data when ECS configuration is incomplete.
DATA_SOURCE = os.getenv("DATA_SOURCE", "fake").strip().lower()

RDS_HOST = os.getenv("RDS_HOST", "")
RDS_PORT = int(os.getenv("RDS_PORT") or "3306")
RDS_DATABASE = os.getenv("RDS_DATABASE", "")
RDS_USER = os.getenv("RDS_USER", "")
RDS_PASSWORD = os.getenv("RDS_PASSWORD", "")
RDS_SSL_CA = os.getenv("RDS_SSL_CA", "")

# US1.1 route planning. Secrets stay in local/ECS environment variables and
# must never be committed to the repository.
ORS_API_KEY = os.getenv("ORS_API_KEY", "")
ORS_BASE_URL = os.getenv(
    "ORS_BASE_URL",
    "https://api.heigit.org/openrouteservice/v2/directions/foot-walking/geojson",
)
GTFS_URL = os.getenv(
    "GTFS_URL",
    "https://opendata.transport.vic.gov.au/dataset/3f4e292e-7f8a-4ffe-831f-1953be0fe448/"
    "resource/fb152201-859f-4882-9206-b768060b50ad/download/gtfs.zip",
)

SENSOR_MATCH_RADIUS_M = float(os.getenv("SENSOR_MATCH_RADIUS_M") or "120")
MINIMUM_SENSOR_COVERAGE = float(os.getenv("MINIMUM_SENSOR_COVERAGE") or "0.20")
HIGH_SENSORY_THRESHOLD = float(os.getenv("HIGH_SENSORY_THRESHOLD") or "600")
TRANSIT_RADIUS_M = float(os.getenv("TRANSIT_RADIUS_M") or "250")
ROUTE_SAMPLE_INTERVAL_M = float(os.getenv("ROUTE_SAMPLE_INTERVAL_M") or "80")
UPSTREAM_TIMEOUT_SECONDS = float(os.getenv("UPSTREAM_TIMEOUT_SECONDS") or "20")
SENSORY_RDS_CACHE_SECONDS = float(os.getenv("SENSORY_RDS_CACHE_SECONDS") or "60")
MAX_RECENT_COUNT_AGE_MINUTES = float(
    os.getenv("MAX_RECENT_COUNT_AGE_MINUTES") or "30"
)
