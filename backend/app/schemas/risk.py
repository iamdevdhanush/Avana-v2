from typing import List, Optional, Dict
from datetime import datetime

from pydantic import BaseModel


class RiskScoreRequest(BaseModel):
    latitude: float
    longitude: float


class RiskFactors(BaseModel):
    historical_risk: float = 0.0
    recent_reports_impact: float = 0.0
    night_factor: float = 0.0
    severity_penalty: float = 0.0
    police_presence_bonus: float = 0.0
    hospital_access_bonus: float = 0.0
    population_density_factor: float = 0.0
    final_score: float = 0.0


class RiskScoreResponse(BaseModel):
    score: float
    category: str
    factors: RiskFactors
    recommendations: List[str] = []


class HeatmapRequest(BaseModel):
    sw_lat: float
    sw_lng: float
    ne_lat: float
    ne_lng: float
    zoom: int = 10
    min_score: float = 0


class HeatmapPoint(BaseModel):
    latitude: float
    longitude: float
    weight: float
    risk_category: str
    intensity: float = 0.0
    radius: int = 20


class DistrictSummary(BaseModel):
    district: str
    avg_score: float
    total_incidents: int
    trend: str


class HeatmapResponse(BaseModel):
    points: List[HeatmapPoint]
    generated_at: str
    district_summaries: Optional[List[DistrictSummary]] = None


# ── Explainability schemas ────────────────────────────────────────────────────

class ExplainRequest(BaseModel):
    latitude: float
    longitude: float
    radius_km: float = 1.0


class ExplainSourceItem(BaseModel):
    title: Optional[str] = None
    incident_type: str
    severity: str
    date: str
    source: str
    source_url: Optional[str] = None
    distance_meters: float = 0.0
    women_safety_category: Optional[str] = None
    publisher: Optional[str] = None
    dataset_name: Optional[str] = None
    dataset_year: Optional[int] = None
    dataset_district: Optional[str] = None


class ExplainResponse(BaseModel):
    risk_score: float
    risk_category: str
    incident_count: int
    sources: List[ExplainSourceItem] = []
