from typing import TypedDict, List, Optional
from langgraph.graph import StateGraph, END
import logging
import asyncio
from sqlalchemy import text

from app.services.nominatim import NominatimService
from app.database import async_session_factory

logger = logging.getLogger(__name__)

nominatim_service = NominatimService()


class GeocodingState(TypedDict):
    query: str
    result: Optional[dict]
    cached: bool
    error: Optional[str]


async def check_cache(state: GeocodingState) -> dict:
    query = state.get("query", "").strip().lower()
    if not query:
        return {"error": "empty_query", "cached": False, "result": None}
    async with async_session_factory() as session:
        try:
            result = await session.execute(
                text("""
                    SELECT id, name, address, place_id, latitude, longitude,
                           district, city, taluk, ward, pincode, location_type
                    FROM locations
                    WHERE LOWER(name) = :query
                       OR LOWER(address) LIKE :like_query
                    ORDER BY created_at DESC
                    LIMIT 1
                """),
                {"query": query, "like_query": f"%{query}%"},
            )
            row = result.fetchone()
            if row:
                cached_result = {
                    "id": str(row[0]),
                    "name": row[1],
                    "address": row[2],
                    "place_id": row[3],
                    "latitude": float(row[4]),
                    "longitude": float(row[5]),
                    "district": row[6],
                    "city": row[7],
                    "taluk": row[8],
                    "ward": row[9],
                    "pincode": row[10],
                    "location_type": row[11],
                }
                logger.info(f"Cache hit for query: {query}")
                return {"result": cached_result, "cached": True}
        except Exception as e:
            logger.warning(f"Cache lookup failed for '{query}': {e}")
    logger.info(f"Cache miss for query: {query}")
    return {"cached": False, "result": None}


async def geocode_query(state: GeocodingState) -> dict:
    if state.get("cached"):
        return {}
    query = state.get("query", "")
    try:
        result = await nominatim_service.geocode(f"{query}, Karnataka, India")
        if result:
            return {"result": result, "error": None}
        else:
            logger.warning(f"No geocoding result for: {query}")
            return {"result": None, "error": "no_results"}
    except Exception as e:
        logger.error(f"Geocoding error for '{query}': {e}")
        return {"result": None, "error": str(e)}


async def parse_result(state: GeocodingState) -> dict:
    if state.get("cached") or not state.get("result"):
        return {}
    raw = state["result"]
    parsed = {
        "latitude": float(raw.get("lat", 0)),
        "longitude": float(raw.get("lng", 0)),
        "display_name": raw.get("display_name", ""),
        "place_id": str(raw.get("place_id", "")),
        "name": state["query"],
    }
    display_parts = parsed["display_name"].split(",")
    if len(display_parts) >= 2:
        parsed["city"] = display_parts[0].strip()
    if len(display_parts) >= 4:
        parsed["district"] = display_parts[-4].strip()
    if len(display_parts) >= 3:
        parsed["taluk"] = display_parts[-3].strip()
    if len(display_parts) >= 1:
        pincode_candidate = display_parts[-1].strip()
        if pincode_candidate.isdigit() and len(pincode_candidate) == 6:
            parsed["pincode"] = pincode_candidate
    return {"result": parsed}


async def cache_result(state: GeocodingState) -> dict:
    if state.get("cached") or not state.get("result"):
        return {}
    result = state["result"]
    async with async_session_factory() as session:
        try:
            lat = result.get("latitude", 0)
            lng = result.get("longitude", 0)
            await session.execute(
                text("""
                    INSERT INTO locations (name, address, place_id, latitude, longitude,
                                           geom, district, city, taluk, pincode, location_type,
                                           created_at)
                    VALUES (:name, :address, :place_id, :latitude, :longitude,
                            ST_SetSRID(ST_MakePoint(:lng, :lat), 4326),
                            :district, :city, :taluk, :pincode, :location_type, NOW())
                    ON CONFLICT DO NOTHING
                """),
                {
                    "name": result.get("name", ""),
                    "address": result.get("display_name", ""),
                    "place_id": result.get("place_id", ""),
                    "latitude": lat,
                    "longitude": lng,
                    "lat": lat,
                    "lng": lng,
                    "district": result.get("district", ""),
                    "city": result.get("city", ""),
                    "taluk": result.get("taluk", ""),
                    "pincode": result.get("pincode", ""),
                    "location_type": "geocoded",
                },
            )
            await session.commit()
            logger.info(f"Cached geocoding result for: {result.get('name', '')}")
        except Exception as e:
            logger.error(f"Failed to cache geocoding result: {e}")
    return {}


def build_geocoding_graph() -> StateGraph:
    workflow = StateGraph(GeocodingState)
    workflow.add_node("check_cache", check_cache)
    workflow.add_node("geocode_query", geocode_query)
    workflow.add_node("parse_result", parse_result)
    workflow.add_node("cache_result", cache_result)
    workflow.set_entry_point("check_cache")
    workflow.add_edge("check_cache", "geocode_query")
    workflow.add_edge("geocode_query", "parse_result")
    workflow.add_edge("parse_result", "cache_result")
    workflow.add_edge("cache_result", END)
    return workflow.compile()


_geocoding_graph = build_geocoding_graph()


async def run(query: str) -> dict:
    initial_state: GeocodingState = {
        "query": query,
        "result": None,
        "cached": False,
        "error": None,
    }
    result = await _geocoding_graph.ainvoke(initial_state)
    if result.get("error"):
        logger.warning(f"Geocoding failed for '{query}': {result['error']}")
    else:
        logger.info(f"Geocoded '{query}' -> ({result.get('result', {}).get('latitude')}, {result.get('result', {}).get('longitude')})")
    return result


async def batch_geocode(queries: List[str]) -> List[dict]:
    results = []
    for query in queries:
        try:
            result = await run(query)
            results.append(result)
        except Exception as e:
            logger.error(f"Batch geocoding failed for '{query}': {e}")
            results.append({"query": query, "result": None, "cached": False, "error": str(e)})
    return results
