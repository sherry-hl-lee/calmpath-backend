from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class LocationInput(BaseModel):
    """A map location supplied by the frontend."""

    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)


class RouteCompareRequest(BaseModel):
    origin: LocationInput
    destination: LocationInput
    travel_time: Optional[datetime] = None


class CrowdEstimate(BaseModel):
    score: float
    congestion_level: str
    source: str
    observation_status: Optional[str] = None
    coverage_status: Optional[str] = None
    as_of: Optional[str] = None
    sensory_indicator: Optional[str] = None


class EdgeResponse(BaseModel):
    edge_id: str
    street_name: Optional[str] = None
    between_street_1: Optional[str] = None
    between_street_2: Optional[str] = None
    length_m: float
    base_walk_cost_seconds: float
    crowd: CrowdEstimate


class RouteResponse(BaseModel):
    route_type: str
    edge_ids: list[str]
    distance_m: float
    walk_time_seconds: float
    crowd_exposure: float
    unknown_edge_count: int
    geometry: dict


class RouteCompareResponse(BaseModel):
    requested_weekday_index: int
    requested_local_hour: int
    origin_node_id: str
    destination_node_id: str
    shortest_route: RouteResponse
    recommended_route: RouteResponse
    recommendation_note: str
