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


class SourceBreakdown(BaseModel):
    police_crime_data: int = 0
    verified_incidents: int = 0
    community_reports: int = 0
    news_intelligence: int = 0


class NewsMetadata(BaseModel):
    title: str
    publisher: str
    published_at: str
    url: str


class PoliceMetadata(BaseModel):
    dataset_name: str
    reporting_year: int
    district: str
    crime_category: str


class ContributingIncidentItem(BaseModel):
    id: str
    incident_type: str
    severity: str
    date: str
    distance_km: float
    source: str
    title: Optional[str] = None
    description: Optional[str] = None
    source_url: Optional[str] = None
    news_metadata: Optional[NewsMetadata] = None
    police_metadata: Optional[PoliceMetadata] = None


class SourceItem(BaseModel):
    name: str
    detail: str
    count: int = 1


class SourceAttribution(BaseModel):
    type: str
    label: str
    count: int
    items: List[SourceItem] = []


class ConfidenceInfo(BaseModel):
    score: float
    based_on: List[str]


class ExplainResponse(BaseModel):
    score: float
    level: str
    trend: str
    last_updated: str
    why_score: SourceBreakdown
    contributing_incidents: List[ContributingIncidentItem]
    sources: List[SourceAttribution]
    confidence: ConfidenceInfo
