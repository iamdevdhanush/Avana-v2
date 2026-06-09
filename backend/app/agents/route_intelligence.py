from typing import TypedDict, List, Optional, Tuple
from langgraph.graph import StateGraph, END
import logging
import json
import asyncio
import httpx

from app.agents.risk_scoring import run as risk_scoring_run

logger = logging.getLogger(__name__)

OSRM_BASE_URL = "https://router.project-osrm.org"
SEGMENT_INTERVAL_METERS = 500


class RouteState(TypedDict):
    source: Tuple[float, float]
    destination: Tuple[float, float]
    routes: List[dict]
    scored_segments: List[dict]
    safest_route: Optional[dict]
    fastest_route: Optional[dict]
    balanced_route: Optional[dict]
    errors: List[str]


def _decode_polyline(encoded: str) -> List[Tuple[float, float]]:
    points = []
    index = 0
    lat = 0
    lng = 0
    while index < len(encoded):
        shift = 0
        result = 0
        while True:
            b = ord(encoded[index]) - 63
            index += 1
            result |= (b & 0x1F) << shift
            shift += 5
            if b < 0x20:
                break
        dlat = ~(result >> 1) if (result & 1) else (result >> 1)
        lat += dlat
        shift = 0
        result = 0
        while True:
            b = ord(encoded[index]) - 63
            index += 1
            result |= (b & 0x1F) << shift
            shift += 5
            if b < 0x20:
                break
        dlng = ~(result >> 1) if (result & 1) else (result >> 1)
        lng += dlng
        points.append((lat / 1e5, lng / 1e5))
    return points


def _interpolate_segments(
    coords: List[Tuple[float, float]],
    interval_meters: int = SEGMENT_INTERVAL_METERS,
) -> List[dict]:
    if not coords:
        return []
    segments = []
    accumulated = 0.0
    segment_coords = [coords[0]]
    for i in range(1, len(coords)):
        lat1, lng1 = coords[i - 1]
        lat2, lng2 = coords[i]
        dlat = lat2 - lat1
        dlng = lng2 - lng1
        dist = (dlat ** 2 + dlng ** 2) ** 0.5 * 111320
        accumulated += dist
        segment_coords.append(coords[i])
        if accumulated >= interval_meters or i == len(coords) - 1:
            mid_idx = len(segment_coords) // 2
            mid_lat, mid_lng = segment_coords[mid_idx]
            segments.append({
                "start": segment_coords[0],
                "end": segment_coords[-1],
                "midpoint": (mid_lat, mid_lng),
                "length_meters": round(accumulated, 2),
                "start_index": i - len(segment_coords) + 1,
                "end_index": i,
            })
            segment_coords = [coords[i]]
            accumulated = 0.0
    return segments


async def fetch_routes(state: RouteState) -> dict:
    src_lat, src_lng = state["source"]
    dst_lat, dst_lng = state["destination"]
    coord_str = f"{src_lng},{src_lat};{dst_lng},{dst_lat}"
    profiles = ["driving", "walking", "cycling"]
    routes = []
    async with httpx.AsyncClient(timeout=30.0) as client:
        for profile in profiles:
            try:
                url = (
                    f"{OSRM_BASE_URL}/{profile}/v1/driving/{coord_str}"
                    f"?overview=full&geometries=geojson&steps=false&alternatives=true"
                )
                response = await client.get(url)
                if response.status_code != 200:
                    logger.warning(f"OSRM {profile} returned {response.status_code}")
                    continue
                data = response.json()
                if data.get("code") != "Ok":
                    logger.warning(f"OSRM {profile} error: {data.get('message', 'unknown')}")
                    continue
                for idx, route_data in enumerate(data.get("routes", [])):
                    geometry = route_data.get("geometry", {})
                    coords_raw = geometry.get("coordinates", [])
                    coords = [(c[1], c[0]) for c in coords_raw]
                    route = {
                        "profile": profile,
                        "alternative_index": idx,
                        "coordinates": coords,
                        "distance_meters": route_data.get("distance", 0),
                        "duration_seconds": route_data.get("duration", 0),
                        "polyline": route_data.get("geometry", {}),
                    }
                    routes.append(route)
            except Exception as e:
                logger.error(f"Failed to fetch {profile} route: {e}")
    logger.info(f"Fetched {len(routes)} route(s) from OSRM")
    return {"routes": routes}


async def segment_routes(state: RouteState) -> dict:
    routes = state.get("routes", [])
    for route in routes:
        coords = route.get("coordinates", [])
        route["segments"] = _interpolate_segments(coords, SEGMENT_INTERVAL_METERS)
        route["segment_count"] = len(route["segments"])
    logger.info(f"Segmented {len(routes)} routes")
    return {"routes": routes}


async def score_segments(state: RouteState) -> dict:
    routes = state.get("routes", [])
    all_scored = []
    for route in routes:
        segments = route.get("segments", [])
        scored_segments = []
        batch_size = 10
        for i in range(0, len(segments), batch_size):
            batch = segments[i:i + batch_size]
            tasks = []
            for seg in batch:
                mid = seg["midpoint"]
                tasks.append(risk_scoring_run(mid[0], mid[1]))
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for seg, result in zip(batch, results):
                if isinstance(result, Exception):
                    logger.error(f"Segment scoring failed: {result}")
                    seg["score"] = 50.0
                    seg["risk_category"] = "Moderate"
                else:
                    seg["score"] = result.get("score", 50.0)
                    seg["risk_category"] = result.get("category", "Moderate")
                    seg["risk_factors"] = result.get("factors", {})
                scored_segments.append(seg)
        route["scored_segments"] = scored_segments
        all_scored.extend(scored_segments)
    logger.info(f"Scored {len(all_scored)} route segments")
    return {"scored_segments": all_scored, "routes": routes}


async def rank_routes(state: RouteState) -> dict:
    routes = state.get("routes", [])
    for route in routes:
        segments = route.get("scored_segments", [])
        if not segments:
            route["avg_safety_score"] = 50.0
            route["min_safety_score"] = 50.0
            route["total_risk_exposure"] = 0.0
            continue
        scores = [s.get("score", 50.0) for s in segments]
        route["avg_safety_score"] = round(sum(scores) / len(scores), 2)
        route["min_safety_score"] = round(min(scores), 2)
        low_score_segments = sum(1 for s in scores if s < 40)
        route["total_risk_exposure"] = round(
            low_score_segments / len(scores) * 100, 2
        )
    if not routes:
        return {
            "safest_route": None,
            "fastest_route": None,
            "balanced_route": None,
        }
    safest = max(routes, key=lambda r: r.get("avg_safety_score", 0))
    fastest = min(routes, key=lambda r: r.get("duration_seconds", float("inf")))
    def _balance_score(r):
        safety = r.get("avg_safety_score", 50) / 100.0
        duration = r.get("duration_seconds", 3600)
        norm_duration = max(0, 1 - duration / 7200)
        return safety * 0.6 + norm_duration * 0.4
    balanced = max(routes, key=_balance_score)
    return {
        "safest_route": safest,
        "fastest_route": fastest,
        "balanced_route": balanced,
    }


def build_route_graph() -> StateGraph:
    workflow = StateGraph(RouteState)
    workflow.add_node("fetch_routes", fetch_routes)
    workflow.add_node("segment_routes", segment_routes)
    workflow.add_node("score_segments", score_segments)
    workflow.add_node("rank_routes", rank_routes)
    workflow.set_entry_point("fetch_routes")
    workflow.add_edge("fetch_routes", "segment_routes")
    workflow.add_edge("segment_routes", "score_segments")
    workflow.add_edge("score_segments", "rank_routes")
    workflow.add_edge("rank_routes", END)
    return workflow.compile()


_route_graph = build_route_graph()


async def run(
    source: Tuple[float, float],
    destination: Tuple[float, float],
) -> dict:
    initial_state: RouteState = {
        "source": source,
        "destination": destination,
        "routes": [],
        "scored_segments": [],
        "safest_route": None,
        "fastest_route": None,
        "balanced_route": None,
        "errors": [],
    }
    result = await _route_graph.ainvoke(initial_state)
    sc = result.get("safest_route", {})
    fc = result.get("fastest_route", {})
    bc = result.get("balanced_route", {})
    logger.info(
        f"Route intelligence: safest={sc.get('avg_safety_score', 'N/A')}, "
        f"fastest={fc.get('duration_seconds', 'N/A')}s, "
        f"balanced={bc.get('avg_safety_score', 'N/A')}"
    )
    return {
        "safest_route": {
            "profile": sc.get("profile"),
            "distance_meters": sc.get("distance_meters"),
            "duration_seconds": sc.get("duration_seconds"),
            "avg_safety_score": sc.get("avg_safety_score"),
            "min_safety_score": sc.get("min_safety_score"),
            "segments": sc.get("scored_segments", []),
        } if sc else None,
        "fastest_route": {
            "profile": fc.get("profile"),
            "distance_meters": fc.get("distance_meters"),
            "duration_seconds": fc.get("duration_seconds"),
            "avg_safety_score": fc.get("avg_safety_score"),
            "segments": fc.get("scored_segments", []),
        } if fc else None,
        "balanced_route": {
            "profile": bc.get("profile"),
            "distance_meters": bc.get("distance_meters"),
            "duration_seconds": bc.get("duration_seconds"),
            "avg_safety_score": bc.get("avg_safety_score"),
            "segments": bc.get("scored_segments", []),
        } if bc else None,
        "all_routes": [
            {
                "profile": r["profile"],
                "distance_meters": r["distance_meters"],
                "duration_seconds": r["duration_seconds"],
                "avg_safety_score": r.get("avg_safety_score"),
                "min_safety_score": r.get("min_safety_score"),
            }
            for r in result.get("routes", [])
        ],
    }
