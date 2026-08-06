import os
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")

REFUGE_DATA_PATH = Path(
    os.getenv("REFUGE_DATA_PATH", "app/data/refuge_candidates.csv")
)
if not REFUGE_DATA_PATH.is_absolute():
    REFUGE_DATA_PATH = PROJECT_ROOT / REFUGE_DATA_PATH
CITY_OF_MELBOURNE_STREET_ADDRESSES_URL = (
    "https://data.melbourne.vic.gov.au/api/explore/v2.1/catalog/datasets/"
    "street-addresses/records"
)
