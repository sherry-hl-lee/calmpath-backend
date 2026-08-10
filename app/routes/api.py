from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException, Query, Request

from app.config import (
    LIVE_REQUEST_WINDOW_MINUTES,
    MELBOURNE_TIMEZONE,
    MINIMUM_CROWD_COVERAGE_FOR_RECOMMENDATION,
)
from app.schemas import EdgeResponse, RouteCompareRequest, RouteCompareResponse
from app.services.routing_service import RoutingService

router = APIRouter()


def service(request: Request) -> RoutingService:
    return request.app.state.routing_service


def requested_time(travel_time: datetime | None) -> datetime:
    local_zone = ZoneInfo(MELBOURNE_TIMEZONE)
    if travel_time is None:
        return datetime.now(local_zone)
    return travel_time.replace(tzinfo=local_zone) if travel_time.tzinfo is None else travel_time.astimezone(local_zone)


def can_use_current_data(travel_time: datetime | None, local_moment: datetime) -> bool:
    """Live observations describe now, not a past/future planned trip."""
    if travel_time is None:
        return True
    now = datetime.now(ZoneInfo(MELBOURNE_TIMEZONE))
    return abs((local_moment - now).total_seconds()) <= LIVE_REQUEST_WINDOW_MINUTES * 60


@router.get("/health")
def health(request: Request):
    repository = request.app.state.repository
    return {
        "status": "ok",
        "nodes": len(repository.nodes),
        "edges": len(repository.edges),
        "historical_patterns": len(repository.patterns),
        "current_contexts": len(repository.contexts),
    }


@router.get("/edges/{edge_id}", response_model=EdgeResponse)
def get_edge(
    edge_id: str,
    request: Request,
    weekday_index: int = Query(default=0, ge=0, le=6),
    local_hour: int = Query(default=12, ge=0, le=23),
):
    routing = service(request)
    routing.repository.refresh_current_contexts()
    edge = routing.repository.edges.get(edge_id)
    if edge is None:
        raise HTTPException(status_code=404, detail="Edge not found.")
    crowd = routing.crowd_for_edge(edge_id, weekday_index, local_hour)
    return {
        "edge_id": edge.edge_id,
        "street_name": edge.street_name,
        "between_street_1": edge.between_street_1,
        "between_street_2": edge.between_street_2,
        "length_m": edge.length_m,
        "base_walk_cost_seconds": edge.walk_seconds,
        "crowd": {
            "score": crowd.score,
            "congestion_level": crowd.level,
            "source": crowd.source,
            "observation_status": crowd.observation_status,
            "coverage_status": crowd.coverage_status,
            "as_of": crowd.as_of,
            "sensory_indicator": crowd.sensory_indicator,
        },
    }


@router.post("/routes/compare", response_model=RouteCompareResponse)
def compare_routes(payload: RouteCompareRequest, request: Request):
    routing = service(request)
    moment = requested_time(payload.travel_time)
    use_current = can_use_current_data(payload.travel_time, moment)
    try:
        if use_current:
            routing.repository.refresh_current_contexts()
        origin = routing.nearest_node(payload.origin.latitude, payload.origin.longitude)
        destination = routing.nearest_node(payload.destination.latitude, payload.destination.longitude)
        shortest = routing.shortest_path(origin, destination, lambda arc: arc.walk_seconds)
        recommended = routing.shortest_path(
            origin,
            destination,
            lambda arc: arc.walk_seconds
            + routing.crowd_for_edge(
                arc.edge_id, moment.weekday(), moment.hour, use_current
            ).score,
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error

    shortest_summary = routing.route_summary(
        shortest, "shortest", moment.weekday(), moment.hour, use_current
    )
    recommended_summary = routing.route_summary(
        recommended, "sensory_recommended", moment.weekday(), moment.hour, use_current
    )
    minimum_coverage = min(
        shortest_summary["data_coverage_ratio"], recommended_summary["data_coverage_ratio"]
    )
    if minimum_coverage < MINIMUM_CROWD_COVERAGE_FOR_RECOMMENDATION:
        note = (
            "Insufficient crowd-data coverage to make a reliable low-crowd recommendation. "
            "Unknown-edge penalties influenced route selection."
        )
    elif recommended_summary["crowd_exposure"] < shortest_summary["crowd_exposure"]:
        note = "Recommended route has lower estimated crowd exposure than the shortest route."
    else:
        note = "The shortest route is also the lowest-cost sensory route for the available data."
    return {
        "requested_weekday_index": moment.weekday(),
        "requested_local_hour": moment.hour,
        "current_data_used": use_current,
        "origin_node_id": origin,
        "destination_node_id": destination,
        "shortest_route": shortest_summary,
        "recommended_route": recommended_summary,
        "recommendation_note": note,
    }
