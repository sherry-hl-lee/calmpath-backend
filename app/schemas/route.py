from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class SensoryIndicator(str, Enum):
    HIGH = "High"
    LOW = "Low"
    LIMITED_DATA = "Limited Data"


class TransitAccessPoint(BaseModel):
    id: str
    name: str
    type: str
    latitude: float
    longitude: float
    distance_to_route_m: float


class RouteOption(BaseModel):
    id: str
    distance_m: float
    duration_s: float
    sensory_indicator: SensoryIndicator
    sensory_score: float | None
    sensor_coverage: float = Field(ge=0, le=1)
    sensors_used: int = Field(ge=0)
    nearby_transport: list[TransitAccessPoint]
    geometry: dict[str, Any]


class RouteResponse(BaseModel):
    routes: list[RouteOption]

