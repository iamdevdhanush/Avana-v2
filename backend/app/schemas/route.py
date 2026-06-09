from typing import List, Tuple

from pydantic import BaseModel


class RouteRequest(BaseModel):
    source_lat: float
    source_lng: float
    dest_lat: float
    dest_lng: float
    profile: str = "driving"


class RouteSegment(BaseModel):
    start_lat: float
    start_lng: float
    end_lat: float
    end_lng: float
    safety_score: float
    risk_category: str
    distance_m: float


class RouteOption(BaseModel):
    type: str
    duration_minutes: float
    distance_km: float
    safety_score: float
    segments: List[RouteSegment]
    geometry: List[List[float]]


class RouteResponse(BaseModel):
    source: Tuple[float, float]
    destination: Tuple[float, float]
    safest: RouteOption
    fastest: RouteOption
    balanced: RouteOption
