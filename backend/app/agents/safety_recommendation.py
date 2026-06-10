from typing import TypedDict, List, Optional
from langgraph.graph import StateGraph, END
import logging
import json
from datetime import datetime, timezone
from sqlalchemy import text

from app.services.gemini import GeminiService
from app.database import async_session_factory
from app.agents.risk_scoring import run as risk_scoring_run

logger = logging.getLogger(__name__)

gemini_service = GeminiService()


class RecommendationState(TypedDict):
    location: tuple
    user_id: Optional[str]
    context: dict
    recommendations: List[str]
    errors: List[str]


async def load_context(state: RecommendationState) -> dict:
    lat, lng = state["location"]
    context = {}
    risk_result = await risk_scoring_run(lat, lng)
    context["risk_score"] = risk_result.get("score")
    context["risk_category"] = risk_result.get("category")
    context["risk_factors"] = risk_result.get("factors", {})
    current_hour = datetime.now(timezone.utc).hour
    context["current_hour"] = current_hour
    context["is_night"] = current_hour >= 21 or current_hour < 6
    async with async_session_factory() as session:
        try:
            nearby_incidents = await session.execute(
                text("""
                    SELECT incident_type, severity, description,
                           ST_Distance(
                               geom::geography,
                               ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography
                           ) as dist_meters
                    FROM incidents
                    WHERE ST_DWithin(
                        geom::geography,
                        ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography,
                        2000
                    )
                    AND status = 'verified'
                    ORDER BY dist_meters ASC
                    LIMIT 5
                """),
                {"lng": lng, "lat": lat},
            )
            context["nearby_incidents"] = [
                {
                    "type": r[0],
                    "severity": r[1],
                    "description": r[2],
                    "distance_meters": round(float(r[3]), 1),
                }
                for r in nearby_incidents.fetchall()
            ]
        except Exception as e:
            logger.error(f"Failed to load nearby incidents: {e}")
            context["nearby_incidents"] = []
        try:
            police_result = await session.execute(
                text("""
                    SELECT name, address,
                           ST_Distance(
                               geom::geography,
                               ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography
                           ) as dist_meters
                    FROM police_stations
                    WHERE ST_DWithin(
                        geom::geography,
                        ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography,
                        2000
                    )
                    ORDER BY dist_meters ASC
                    LIMIT 3
                """),
                {"lng": lng, "lat": lat},
            )
            context["nearby_police"] = [
                {
                    "name": r[0],
                    "address": r[1],
                    "distance_meters": round(float(r[2]), 1),
                }
                for r in police_result.fetchall()
            ]
        except Exception as e:
            logger.error(f"Failed to load police stations: {e}")
            context["nearby_police"] = []
        try:
            hospital_result = await session.execute(
                text("""
                    SELECT name, address,
                           ST_Distance(
                               geom::geography,
                               ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography
                           ) as dist_meters
                    FROM hospitals
                    WHERE ST_DWithin(
                        geom::geography,
                        ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography,
                        2000
                    )
                    ORDER BY dist_meters ASC
                    LIMIT 3
                """),
                {"lng": lng, "lat": lat},
            )
            context["nearby_hospitals"] = [
                {
                    "name": r[0],
                    "address": r[1],
                    "distance_meters": round(float(r[2]), 1),
                }
                for r in hospital_result.fetchall()
            ]
        except Exception as e:
            logger.error(f"Failed to load hospitals: {e}")
            context["nearby_hospitals"] = []
        if state.get("user_id"):
            try:
                user_result = await session.execute(
                    text("""
                        SELECT created_at, incident_type, severity, latitude, longitude
                        FROM safety_reports
                        WHERE user_id = :user_id::uuid
                        ORDER BY created_at DESC
                        LIMIT 5
                    """),
                    {"user_id": state["user_id"]},
                )
                context["user_history"] = [
                    {
                        "reported_at": r[0].isoformat() if r[0] else None,
                        "type": r[1],
                        "severity": r[2],
                    }
                    for r in user_result.fetchall()
                ]
            except Exception as e:
                logger.warning(f"Failed to load user history: {e}")
                context["user_history"] = []
    return {"context": context}


async def generate_insights(state: RecommendationState) -> dict:
    context = state.get("context", {})
    lat, lng = state["location"]
    hour = context.get("current_hour", 12)
    period = "night" if context.get("is_night") else ("evening" if hour >= 18 else "afternoon" if hour >= 12 else "morning")
    risk_cat = context.get("risk_category", "Moderate")
    incidents = context.get("nearby_incidents", [])
    police = context.get("nearby_police", [])
    hospitals = context.get("nearby_hospitals", [])
    user_history = context.get("user_history", [])
    incidents_summary = "; ".join(
        f"{i['type']} ({i['severity']}) {i['distance_meters']}m away"
        for i in incidents[:3]
    ) if incidents else "No recent incidents nearby"
    police_summary = "; ".join(
        f"{p['name']} {p['distance_meters']}m away"
        for p in police[:2]
    ) if police else "No police stations within 2km"
    hospital_summary = "; ".join(
        f"{h['name']} {h['distance_meters']}m away"
        for h in hospitals[:2]
    ) if hospitals else "No hospitals within 2km"
    prompt = (
        f"Generate safety recommendations for a location in Karnataka, India.\n"
        f"Location: ({lat}, {lng})\n"
        f"Time: {period} (hour {hour})\n"
        f"Risk Level: {risk_cat} (score: {context.get('risk_score', 'N/A')})\n"
        f"Nearby Incidents: {incidents_summary}\n"
        f"Police: {police_summary}\n"
        f"Hospitals: {hospital_summary}\n"
        f"User History: {len(user_history)} past reports\n\n"
        "Return a JSON array of 3-5 specific, actionable safety recommendations. "
        "Each recommendation should have:\n"
        "- title: short title\n"
        "- description: detailed advice (1-2 sentences)\n"
        "- priority: high/medium/low\n"
        "- category: route_safety | time_aware | resource_alert | general_precaution | incident_awareness\n"
        "- icon: emoji icon name (e.g., police, hospital, warning, clock, shield)"
    )
    try:
        response = gemini_service.generate(
            prompt,
            system_instruction=(
                "You are a women's safety recommendation AI for Karnataka, India. "
                "Provide practical, context-aware safety tips based on location risk data. "
                "Return ONLY valid JSON array. No markdown."
            ),
        )
        cleaned = response.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        if cleaned.startswith("```"):
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        recommendations = json.loads(cleaned.strip())
        if isinstance(recommendations, dict):
            recommendations = [recommendations]
    except (json.JSONDecodeError, ValueError) as e:
        logger.error(f"Failed to parse Gemini recommendations: {e}")
        recommendations = _fallback_recommendations(context)
    return {"recommendations": recommendations, "errors": state.get("errors", [])}


def _fallback_recommendations(context: dict) -> List[dict]:
    recs = []
    risk_cat = context.get("risk_category", "Moderate")
    is_night = context.get("is_night", False)
    police = context.get("nearby_police", [])
    hospitals = context.get("nearby_hospitals", [])
    if is_night and risk_cat in ("High Risk", "Critical"):
        recs.append({
            "title": "Avoid this area at night",
            "description": "The area has high risk scores. Consider traveling during daylight hours or using alternative routes.",
            "priority": "high",
            "category": "time_aware",
            "icon": "clock",
        })
    if not police:
        recs.append({
            "title": "No nearby police stations",
            "description": "There are no police stations within 2km. Save emergency contacts and stay alert.",
            "priority": "high",
            "category": "resource_alert",
            "icon": "police",
        })
    if not hospitals:
        recs.append({
            "title": "Medical facilities distant",
            "description": "No hospitals within 2km. Carry a basic first-aid kit and know the nearest medical facility route.",
            "priority": "medium",
            "category": "resource_alert",
            "icon": "hospital",
        })
    if risk_cat in ("High Risk", "Critical"):
        recs.append({
            "title": "Exercise extreme caution",
            "description": f"This area is classified as {risk_cat}. Stay on well-lit main roads, avoid shortcuts, and share your location with trusted contacts.",
            "priority": "high",
            "category": "general_precaution",
            "icon": "warning",
        })
    if context.get("nearby_incidents"):
        recs.append({
            "title": "Recent incidents reported nearby",
            "description": f"There have been recent safety incidents within 2km. Stay aware of your surroundings and report any suspicious activity.",
            "priority": "medium",
            "category": "incident_awareness",
            "icon": "shield",
        })
    if risk_cat in ("Safe", "Moderate"):
        recs.append({
            "title": "Area is relatively safe",
            "description": "The safety score is favorable. Continue practicing standard safety precautions.",
            "priority": "low",
            "category": "general_precaution",
            "icon": "shield",
        })
    return recs


async def structure_recommendations(state: RecommendationState) -> dict:
    recommendations = state.get("recommendations", [])
    if not recommendations:
        recommendations = _fallback_recommendations(state.get("context", {}))
    for rec in recommendations:
        if isinstance(rec, dict):
            rec.setdefault("priority", "medium")
            rec.setdefault("category", "general_precaution")
            rec.setdefault("icon", "shield")
    return {"recommendations": recommendations}


def build_recommendation_graph() -> StateGraph:
    workflow = StateGraph(RecommendationState)
    workflow.add_node("load_context", load_context)
    workflow.add_node("generate_insights", generate_insights)
    workflow.add_node("structure_recommendations", structure_recommendations)
    workflow.set_entry_point("load_context")
    workflow.add_edge("load_context", "generate_insights")
    workflow.add_edge("generate_insights", "structure_recommendations")
    workflow.add_edge("structure_recommendations", END)
    return workflow.compile()


_recommendation_graph = build_recommendation_graph()


async def run(
    lat: float, lng: float,
    user_id: Optional[str] = None,
) -> dict:
    initial_state: RecommendationState = {
        "location": (lat, lng),
        "user_id": user_id,
        "context": {},
        "recommendations": [],
        "errors": [],
    }
    result = await _recommendation_graph.ainvoke(initial_state)
    logger.info(
        f"Generated {len(result.get('recommendations', []))} safety recommendations "
        f"for ({lat}, {lng})"
    )
    return {
        "location": {"latitude": lat, "longitude": lng},
        "risk_score": result.get("context", {}).get("risk_score"),
        "risk_category": result.get("context", {}).get("risk_category"),
        "recommendations": result.get("recommendations", []),
        "context_summary": {
            "is_night": result.get("context", {}).get("is_night"),
            "nearby_incidents": len(result.get("context", {}).get("nearby_incidents", [])),
            "nearby_police": len(result.get("context", {}).get("nearby_police", [])),
            "nearby_hospitals": len(result.get("context", {}).get("nearby_hospitals", [])),
        },
    }
