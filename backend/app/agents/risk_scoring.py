from typing import TypedDict, List, Optional, Tuple
from langgraph.graph import StateGraph, END
import logging
import math
import asyncio
from datetime import datetime
from sqlalchemy import text
from app.database import async_session_factory

logger = logging.getLogger(__name__)

HISTORICAL_RADIUS_METERS = 1000
RECENT_RADIUS_METERS = 1000
POLICE_RADIUS_METERS = 2000
HOSPITAL_RADIUS_METERS = 2000
HISTORICAL_RISK_WEIGHT = 0.4
NIGHT_START_HOUR = 21
NIGHT_END_HOUR = 6
SEVERITY_WEIGHTS = {
    "low": 5,
    "medium": 15,
    "high": 30,
    "critical": 50,
}
POLICE_BUFFER = 10
HOSPITAL_BUFFER = 5


class RiskScoreState(TypedDict):
    latitude: float
    longitude: float
    district: Optional[str]
    score: Optional[float]
    category: Optional[str]
    factors: dict


async def load_context(state: RiskScoreState) -> dict:
    lat = state["latitude"]
    lng = state["longitude"]
    factors = {}
    async with async_session_factory() as session:
        try:
            historical_count = await session.execute(
                text("""
                    SELECT COUNT(*) as cnt,
                           COALESCE(AVG(CASE
                               WHEN severity = 'critical' THEN 50
                               WHEN severity = 'high' THEN 30
                               WHEN severity = 'medium' THEN 15
                               WHEN severity = 'low' THEN 5
                               ELSE 10
                           END), 0) as avg_severity_score
                    FROM incidents
                    WHERE ST_DWithin(
                        geom::geography,
                        ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography,
                        :radius
                    )
                    AND status != 'dismissed'
                """),
                {"lng": lng, "lat": lat, "radius": HISTORICAL_RADIUS_METERS},
            )
            row = historical_count.fetchone()
            factors["historical_incident_count"] = int(row[0]) if row else 0
            factors["avg_severity_score"] = float(row[1]) if row else 0.0
            recent_count = await session.execute(
                text("""
                    SELECT COUNT(*) as cnt
                    FROM incidents
                    WHERE ST_DWithin(
                        geom::geography,
                        ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography,
                        :radius
                    )
                    AND created_at >= NOW() - INTERVAL '7 days'
                    AND status != 'dismissed'
                """),
                {"lng": lng, "lat": lat, "radius": RECENT_RADIUS_METERS},
            )
            row2 = recent_count.fetchone()
            factors["recent_incident_count"] = int(row2[0]) if row2 else 0
            police_count = await session.execute(
                text("""
                    SELECT COUNT(*) as cnt
                    FROM police_stations
                    WHERE ST_DWithin(
                        geom::geography,
                        ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography,
                        :radius
                    )
                """),
                {"lng": lng, "lat": lat, "radius": POLICE_RADIUS_METERS},
            )
            row3 = police_count.fetchone()
            factors["nearby_police_stations"] = int(row3[0]) if row3 else 0
            hospital_count = await session.execute(
                text("""
                    SELECT COUNT(*) as cnt
                    FROM hospitals
                    WHERE ST_DWithin(
                        geom::geography,
                        ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography,
                        :radius
                    )
                """),
                {"lng": lng, "lat": lat, "radius": HOSPITAL_RADIUS_METERS},
            )
            row4 = hospital_count.fetchone()
            factors["nearby_hospitals"] = int(row4[0]) if row4 else 0
            district_row = await session.execute(
                text("""
                    SELECT district FROM incidents
                    WHERE ST_DWithin(
                        geom::geography,
                        ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography,
                        :radius
                    )
                    AND district IS NOT NULL
                    LIMIT 1
                """),
                {"lng": lng, "lat": lat, "radius": HISTORICAL_RADIUS_METERS},
            )
            drow = district_row.fetchone()
            factors["inferred_district"] = drow[0] if drow else state.get("district")
        except Exception as e:
            logger.error(f"Failed to load context at ({lat}, {lng}): {e}")
            factors["error"] = str(e)
    return {"factors": factors, "district": factors.get("inferred_district", state.get("district"))}


async def calculate_historical_risk(state: RiskScoreState) -> dict:
    factors = dict(state.get("factors", {}))
    count = factors.get("historical_incident_count", 0)
    avg_severity = factors.get("avg_severity_score", 0)
    if count == 0:
        factors["historical_risk"] = 0.0
        return {"factors": factors}
    density_factor = min(1.0, count / 50.0)
    severity_factor = avg_severity / 50.0
    historical_risk = (density_factor * 0.6 + severity_factor * 0.4) * 100.0
    factors["historical_risk"] = min(100.0, historical_risk)
    return {"factors": factors}


async def calculate_recent_impact(state: RiskScoreState) -> dict:
    factors = dict(state.get("factors", {}))
    recent_count = factors.get("recent_incident_count", 0)
    if recent_count == 0:
        factors["recent_impact"] = 0.0
        return {"factors": factors}
    impact = min(30.0, recent_count * 8.0)
    factors["recent_impact"] = impact
    return {"factors": factors}


async def calculate_night_factor(state: RiskScoreState) -> dict:
    factors = dict(state.get("factors", {}))
    current_hour = datetime.utcnow().hour
    is_night = current_hour >= NIGHT_START_HOUR or current_hour < NIGHT_END_HOUR
    factors["is_night"] = is_night
    factors["night_penalty"] = 15.0 if is_night else 0.0
    return {"factors": factors}


async def calculate_safety_buffers(state: RiskScoreState) -> dict:
    factors = dict(state.get("factors", {}))
    police = factors.get("nearby_police_stations", 0)
    hospitals = factors.get("nearby_hospitals", 0)
    safety_buffers = 0.0
    if police > 0:
        safety_buffers += POLICE_BUFFER * min(1.0, police / 3.0)
    if hospitals > 0:
        safety_buffers += HOSPITAL_BUFFER * min(1.0, hospitals / 3.0)
    factors["safety_buffers"] = safety_buffers
    return {"factors": factors}


async def calculate_severity_penalty(state: RiskScoreState) -> dict:
    factors = dict(state.get("factors", {}))
    lat = state["latitude"]
    lng = state["longitude"]
    penalty = 0.0
    async with async_session_factory() as session:
        try:
            result = await session.execute(
                text("""
                    SELECT severity, COUNT(*) as cnt
                    FROM incidents
                    WHERE ST_DWithin(
                        geom::geography,
                        ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography,
                        :radius
                    )
                    AND status != 'dismissed'
                    GROUP BY severity
                """),
                {"lng": lng, "lat": lat, "radius": HISTORICAL_RADIUS_METERS},
            )
            rows = result.fetchall()
            total = 0
            for row in rows:
                sev = row[0]
                cnt = int(row[1])
                weight = SEVERITY_WEIGHTS.get(sev, 10)
                penalty += weight * cnt
                total += cnt
            if total > 0:
                penalty = penalty / total
            else:
                penalty = 0.0
        except Exception as e:
            logger.error(f"Severity penalty calculation failed: {e}")
    factors["severity_penalty"] = min(40.0, penalty)
    return {"factors": factors}


async def compute_final_score(state: RiskScoreState) -> dict:
    factors = state.get("factors", {})
    historical_risk = factors.get("historical_risk", 0.0)
    recent_impact = factors.get("recent_impact", 0.0)
    night_penalty = factors.get("night_penalty", 0.0)
    severity_penalty = factors.get("severity_penalty", 0.0)
    safety_buffers = factors.get("safety_buffers", 0.0)
    raw_score = 100.0 - (
        HISTORICAL_RISK_WEIGHT * historical_risk
        + recent_impact
        + night_penalty
        + severity_penalty
    ) + safety_buffers
    score = max(0.0, min(100.0, raw_score))
    if score <= 30:
        category = "Safe"
    elif score <= 60:
        category = "Moderate"
    elif score <= 80:
        category = "High Risk"
    else:
        category = "Critical"
    factors["final_raw"] = round(raw_score, 2)
    factors["historical_risk_weighted"] = round(HISTORICAL_RISK_WEIGHT * historical_risk, 2)
    return {
        "score": round(score, 2),
        "category": category,
        "factors": factors,
    }


def build_risk_graph() -> StateGraph:
    workflow = StateGraph(RiskScoreState)
    workflow.add_node("load_context", load_context)
    workflow.add_node("calculate_historical_risk", calculate_historical_risk)
    workflow.add_node("calculate_recent_impact", calculate_recent_impact)
    workflow.add_node("calculate_night_factor", calculate_night_factor)
    workflow.add_node("calculate_safety_buffers", calculate_safety_buffers)
    workflow.add_node("calculate_severity_penalty", calculate_severity_penalty)
    workflow.add_node("compute_final_score", compute_final_score)
    workflow.set_entry_point("load_context")
    workflow.add_edge("load_context", "calculate_historical_risk")
    workflow.add_edge("calculate_historical_risk", "calculate_recent_impact")
    workflow.add_edge("calculate_recent_impact", "calculate_night_factor")
    workflow.add_edge("calculate_night_factor", "calculate_safety_buffers")
    workflow.add_edge("calculate_safety_buffers", "calculate_severity_penalty")
    workflow.add_edge("calculate_severity_penalty", "compute_final_score")
    workflow.add_edge("compute_final_score", END)
    return workflow.compile()


_risk_graph = build_risk_graph()


async def run(lat: float, lng: float, district: Optional[str] = None) -> dict:
    initial_state: RiskScoreState = {
        "latitude": lat,
        "longitude": lng,
        "district": district,
        "score": None,
        "category": None,
        "factors": {},
    }
    result = await _risk_graph.ainvoke(initial_state)
    logger.info(
        f"Risk score for ({lat}, {lng}): {result['score']} ({result['category']})"
    )
    return result


async def batch_calculate(points: List[Tuple[float, float]]) -> List[dict]:
    results = []
    for lat, lng in points:
        try:
            result = await run(lat, lng)
            results.append(result)
        except Exception as e:
            logger.error(f"Batch risk scoring failed for ({lat}, {lng}): {e}")
            results.append({
                "latitude": lat,
                "longitude": lng,
                "score": None,
                "category": "Error",
                "factors": {"error": str(e)},
            })
    return results
