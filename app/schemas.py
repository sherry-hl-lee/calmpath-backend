from datetime import datetime
from typing import Literal, Optional

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
    score: Optional[float] = None
    score_unit: Literal["pedestrians_per_minute"]
    routing_penalty: Optional[float] = None
    congestion_level: Literal["LOW", "MEDIUM", "HIGH", "UNKNOWN"]
    source: Literal["current_observation", "historical_pattern", "unknown"]
    observation_status: Optional[str] = None
    coverage_status: Optional[str] = None
    evaluated_at: Optional[str] = None
    observed_at: Optional[str] = None
    sensor_count: Optional[int] = None
    aggregation_method: Optional[Literal["maximum"]] = None
    sensory_indicator: Optional[str] = None


class EdgeResponse(BaseModel):
    edge_id: str
    street_name: Optional[str] = None
    between_street_1: Optional[str] = None
    between_street_2: Optional[str] = None
    length_m: float
    base_walk_cost_seconds: float
    crowd: CrowdEstimate


class RouteSegmentResponse(BaseModel):
    edge_id: str
    sequence: int = Field(ge=1)
    street_name: Optional[str] = None
    distance_m: float
    walk_time_seconds: float
    crowd_score: Optional[float] = None
    crowd_score_unit: Literal["pedestrians_per_minute"]
    routing_penalty: Optional[float] = None
    crowd_level: Literal["LOW", "MEDIUM", "HIGH", "UNKNOWN"]
    sensory_level: Literal["LOW", "MEDIUM", "HIGH", "UNKNOWN"]
    limited_data: bool
    # Compatibility alias for clients using the earlier edge response name.
    congestion_level: Literal["LOW", "MEDIUM", "HIGH", "UNKNOWN"]
    crowd_source: Literal["current_observation", "historical_pattern", "unknown"]
    observation_status: Optional[str] = None
    coverage_status: Optional[str] = None
    evaluated_at: Optional[str] = None
    observed_at: Optional[str] = None
    sensor_count: Optional[int] = None
    aggregation_method: Optional[Literal["maximum"]] = None
    geometry: dict


class CrowdExposureRange(BaseModel):
    minimum: float = 0.0
    maximum: Optional[float] = None


class RouteResponse(BaseModel):
    route_type: str
    edge_ids: list[str]
    distance_m: float
    walk_time_seconds: float
    crowd_exposure: Optional[float] = None
    crowd_exposure_unit: Literal["pedestrians_per_minute"]
    crowd_exposure_range: CrowdExposureRange
    crowd_level: Optional[Literal["LOW", "MEDIUM", "HIGH"]] = None
    sensory_level: Optional[Literal["LOW", "MEDIUM", "HIGH"]] = None
    sensory_level_basis: Literal["PEDESTRIAN_CROWD_ONLY"]
    limited_data: bool
    minimum_required_coverage_ratio: float
    crowd_threshold_version: Literal["provisional-dmp-v1"]
    routing_crowd_cost: float
    known_edge_count: int
    unknown_edge_count: int
    known_distance_m: float
    unknown_distance_m: float
    total_distance_m: float
    data_coverage_ratio: float
    congested_segment_count: int
    has_congestion_warning: bool
    segments: list[RouteSegmentResponse]
    geometry: dict


class RouteCompareResponse(BaseModel):
    requested_weekday_index: int
    requested_local_hour: int
    current_data_used: bool
    origin_node_id: str
    destination_node_id: str
    shortest_route: RouteResponse
    recommended_route: RouteResponse
    recommendation_status: Literal[
        "LOWER_CROWD",
        "SHORTEST_ALREADY_BEST",
        "INSUFFICIENT_DATA",
        "NO_ALTERNATIVE",
    ]
    recommended_route_is_distinct: bool
    crowd_exposure_reduction_percent: Optional[float] = None
    warning: Optional[str] = None
    data_as_of: Optional[str] = None
    recommendation_note: str
