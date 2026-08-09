from pathlib import Path
import os


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = Path(os.getenv("DATA_DIR", PROJECT_ROOT / "data"))
MELBOURNE_TIMEZONE = "Australia/Melbourne"

# Prototype values only. They must be calibrated before a production release.
UNKNOWN_CROWD_PENALTY = 75.0
CROWD_WEIGHT_SECONDS = 1.0
