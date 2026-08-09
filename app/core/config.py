import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")

RDS_HOST = os.getenv("RDS_HOST", "")
RDS_PORT = int(os.getenv("RDS_PORT") or "3306")
RDS_DATABASE = os.getenv("RDS_DATABASE", "")
RDS_USER = os.getenv("RDS_USER", "")
RDS_PASSWORD = os.getenv("RDS_PASSWORD", "")
