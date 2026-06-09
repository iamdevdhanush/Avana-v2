from typing import TypedDict, List, Optional
from langgraph.graph import StateGraph, END
import logging
from datetime import datetime
import asyncio
import math
from sqlalchemy import text

from app.database import async_session_factory
from app.agents.risk_scoring import run as risk_scoring_run

logger = logging.getLogger(__name__)


GRID_SIZES = {
    "district": 0.018,  # ~2km
    "city": 0.0045,     # ~500m
    "ward": 0.0009,     # ~100m
}

DISTRICT_BOUNDS = {
    "Bengaluru Urban": (12.8, 13.2, 77.4, 77.8),
    "Bengaluru Rural": (13.0, 13.4, 77.2, 77.7),
    "Mysuru": (12.1, 12.5, 76.5, 76.8),
    "Dakshina Kannada": (12.7, 13.2, 74.8, 75.2),
    "Belagavi": (15.5, 16.2, 74.2, 75.1),
    "Dharwad": (15.3, 15.6, 74.8, 75.2),
    "Hubballi": (15.3, 15.4, 74.9, 75.1),
    "Mangaluru": (12.8, 13.0, 74.8, 74.9),
    "Udupi": (13.3, 13.4, 74.7, 74.8),
    "Shivamogga": (13.8, 14.0, 75.2, 75.4),
    "Tumakuru": (13.3, 13.4, 77.1, 77.2),
}

CITY_BOUNDS = {
    "Bengaluru": (12.87, 13.1, 77.5, 77.7),
    "Mysuru": (12.28, 12.35, 76.6, 76.68),
    "Mangaluru": (12.84, 12.92, 74.82, 74.9),
    "Hubballi": (15.33, 15.38, 75.1, 75.16),
    "Belagavi": (15.83, 15.88, 74.48, 74.54),
}


class HeatmapState(TypedDict):
    zoom_level: str
    district: Optional[str]
    city: Optional[str]
    grid_points: List[dict]
    heatmap_data: List[dict]
    generated_at: str
    errors: List[str]


def _get_bounds(zoom_level: str, district: Optional[str], city: Optional[str]) -> tuple:
    if zoom_level == "district" and district and district in DISTRICT_BOUNDS:
        return DISTRICT_BOUNDS[district]
    if zoom_level == "city" and city and city in CITY_BOUNDS:
        return CITY_BOUNDS[city]
    if zoom_level == "ward" and city and city in CITY_BOUNDS:
        b = CITY_BOUNDS[city]
        return (b[0], b[1], b[2], b[3])
    return DISTRICT_BOUNDS.get(district, (11.5, 14.5, 74.0, 78.5))


async def determine_grid(state: HeatmapState) -> dict:
    zoom = state.get("zoom_level", "district")
    grid_size = GRID_SIZES.get(zoom, 0.018)
    bounds = _get_bounds(zoom, state.get("district"), state.get("city"))
    min_lat, max_lat, min_lng, max_lng = bounds
    points = []
    lat = min_lat
    while lat <= max_lat:
        lng = min_lng
        while lng <= max_lng:
            points.append({
                "latitude": round(lat, 6),
                "longitude": round(lng, 6),
            })
            lng += grid_size
        lat += grid_size
    logger.info(f"Generated {len(points)} grid points for {zoom} level")
    return {"grid_points": points}


async def calculate_point_scores(state: HeatmapState) -> dict:
    points = state.get("grid_points", [])
    heatmap = []
    batch_size = 10
    for i in range(0, len(points), batch_size):
        batch = points[i:i + batch_size]
        tasks = []
        for pt in batch:
            tasks.append(risk_scoring_run(pt["latitude"], pt["longitude"], state.get("district")))
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for pt, result in zip(batch, results):
            if isinstance(result, Exception):
                logger.error(f"Risk scoring failed for ({pt['latitude']}, {pt['longitude']}): {result}")
                heatmap.append({
                    "latitude": pt["latitude"],
                    "longitude": pt["longitude"],
                    "score": 50.0,
                    "category": "Moderate",
                    "factors": {},
                })
            else:
                heatmap.append({
                    "latitude": pt["latitude"],
                    "longitude": pt["longitude"],
                    "score": result.get("score", 50.0),
                    "category": result.get("category", "Moderate"),
                    "factors": result.get("factors", {}),
                })
    logger.info(f"Scored {len(heatmap)} heatmap points")
    return {"heatmap_data": heatmap}


async def aggregate_results(state: HeatmapState) -> dict:
    data = state.get("heatmap_data", [])
    if not data:
        return {}
    scores = [d["score"] for d in data if d.get("score") is not None]
    if not scores:
        return {}
    min_s = min(scores)
    max_s = max(scores)
    range_s = max_s - min_s if max_s > min_s else 1
    for d in data:
        if d.get("score") is not None:
            d["normalized_score"] = round((d["score"] - min_s) / range_s * 100, 2)
        else:
            d["normalized_score"] = 50.0
    return {"heatmap_data": data}


async def store_heatmap(state: HeatmapState) -> dict:
    data = state.get("heatmap_data", [])
    if not data:
        return {}
    generated_at = datetime.utcnow().isoformat()
    async with async_session_factory() as session:
        try:
            params = []
            for d in data:
                params.append({
                    "latitude": d["latitude"],
                    "longitude": d["longitude"],
                    "score": d.get("score", 50.0),
                    "category": d.get("category", "Moderate"),
                    "zoom_level": state["zoom_level"],
                    "district": state.get("district", ""),
                    "city": state.get("city", ""),
                    "factors": str(d.get("factors", {})),
                    "generated_at": generated_at,
                })
            await session.execute(
                text("""
                    INSERT INTO risk_scores
                        (latitude, longitude, score, category, zoom_level,
                         district, city, factors, generated_at, created_at)
                    VALUES
                        (:latitude, :longitude, :score, :category, :zoom_level,
                         :district, :city, :factors::jsonb, :generated_at::timestamptz, NOW())
                """),
                params,
            )
            await session.commit()
            logger.info(f"Stored {len(params)} heatmap points")
        except Exception as e:
            logger.error(f"Failed to store heatmap data: {e}")
    return {"generated_at": generated_at}


def build_heatmap_graph() -> StateGraph:
    workflow = StateGraph(HeatmapState)
    workflow.add_node("determine_grid", determine_grid)
    workflow.add_node("calculate_point_scores", calculate_point_scores)
    workflow.add_node("aggregate_results", aggregate_results)
    workflow.add_node("store_heatmap", store_heatmap)
    workflow.set_entry_point("determine_grid")
    workflow.add_edge("determine_grid", "calculate_point_scores")
    workflow.add_edge("calculate_point_scores", "aggregate_results")
    workflow.add_edge("aggregate_results", "store_heatmap")
    workflow.add_edge("store_heatmap", END)
    return workflow.compile()


_heatmap_graph = build_heatmap_graph()


async def generate_heatmap(
    zoom_level: str = "district",
    district: Optional[str] = None,
    city: Optional[str] = None,
) -> dict:
    initial_state: HeatmapState = {
        "zoom_level": zoom_level,
        "district": district,
        "city": city,
        "grid_points": [],
        "heatmap_data": [],
        "generated_at": "",
        "errors": [],
    }
    result = await _heatmap_graph.ainvoke(initial_state)
    logger.info(
        f"Heatmap generated: {len(result.get('heatmap_data', []))} points "
        f"at {zoom_level} level"
    )
    return result


async def get_heatmap_data(
    sw_lat: float, sw_lng: float,
    ne_lat: float, ne_lng: float,
    zoom: str = "city",
) -> List[dict]:
    async with async_session_factory() as session:
        try:
            result = await session.execute(
                text("""
                    SELECT DISTINCT ON (latitude, longitude)
                        latitude, longitude, score, category, district, city,
                        factors, generated_at
                    FROM risk_scores
                    WHERE latitude BETWEEN :sw_lat AND :ne_lat
                      AND longitude BETWEEN :sw_lng AND :ne_lng
                      AND zoom_level = :zoom
                    ORDER BY latitude, longitude, generated_at DESC
                """),
                {
                    "sw_lat": sw_lat,
                    "ne_lat": ne_lat,
                    "sw_lng": sw_lng,
                    "ne_lng": ne_lng,
                    "zoom": zoom,
                },
            )
            rows = result.fetchall()
            return [
                {
                    "latitude": float(r[0]),
                    "longitude": float(r[1]),
                    "score": float(r[2]),
                    "category": r[3],
                    "district": r[4],
                    "city": r[5],
                    "generated_at": r[7].isoformat() if r[7] else None,
                }
                for r in rows
            ]
        except Exception as e:
            logger.error(f"Failed to query heatmap data: {e}")
            return []
