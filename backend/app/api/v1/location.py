import logging
import time
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.nominatim import NominatimService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/location", tags=["Location"])

nominatim_service = NominatimService()


class ReverseGeocodeRequest(BaseModel):
    latitude: float
    longitude: float


class ReverseGeocodeResponse(BaseModel):
    display_name: str = ""
    locality: str = ""
    suburb: str = ""
    district: str = ""
    city: str = ""
    state: str = ""
    country: str = ""
    latitude: float
    longitude: float
    cached: bool = False
    response_time_ms: float = 0.0


def _build_display_name(result: dict) -> str:
    locality = result.get("locality") or ""
    suburb = result.get("suburb") or ""
    city = result.get("city") or ""
    district = result.get("district") or ""
    state = result.get("state") or ""

    parts = []
    if locality and city:
        parts.append(f"{locality}, {city}")
    elif city:
        parts.append(city)
    elif locality:
        parts.append(locality)
    elif district:
        parts.append(district)
    elif suburb:
        parts.append(suburb)
    if state:
        parts.append(state)
    return ", ".join(parts) if parts else ""


@router.post("/reverse-geocode", response_model=ReverseGeocodeResponse)
async def reverse_geocode(body: ReverseGeocodeRequest, db: AsyncSession = Depends(get_db)):
    start = time.monotonic()
    lat = round(body.latitude, 4)
    lng = round(body.longitude, 4)
    cache_key = f"reverse:{lat},{lng}"

    try:
        result = await db.execute(
            text("""
                SELECT display_name, latitude, longitude
                FROM geocoding_cache
                WHERE location_text = :key
                  AND last_verified >= NOW() - INTERVAL '30 days'
                LIMIT 1
            """),
            {"key": cache_key},
        )
        cached_row = result.fetchone()
    except Exception as e:
        logger.warning(f"Cache lookup failed: {e}")
        cached_row = None

    if cached_row:
        elapsed = (time.monotonic() - start) * 1000
        logger.info(f"[LOCATION] Cache HIT for ({lat}, {lng}) in {elapsed:.0f}ms")
        try:
            await db.execute(
                text("UPDATE geocoding_cache SET last_verified = NOW() WHERE location_text = :key"),
                {"key": cache_key},
            )
            await db.commit()
        except Exception:
            pass
        return ReverseGeocodeResponse(
            display_name=cached_row[0] or "",
            latitude=cached_row[1],
            longitude=cached_row[2],
            cached=True,
            response_time_ms=round(elapsed, 1),
        )

    geo_result = await nominatim_service.reverse_geocode(lat, lng)

    elapsed = (time.monotonic() - start) * 1000
    logger.info(f"[LOCATION] Reverse geocode ({lat}, {lng}) → {'HIT' if geo_result else 'MISS'} in {elapsed:.0f}ms")

    if not geo_result:
        return ReverseGeocodeResponse(
            latitude=lat,
            longitude=lng,
            display_name=f"{lat}, {lng}",
            cached=False,
            response_time_ms=round(elapsed, 1),
        )

    display_name = _build_display_name(geo_result)

    try:
        await db.execute(
            text("""
                INSERT INTO geocoding_cache (location_text, latitude, longitude, display_name, last_verified, created_at)
                VALUES (:key, :lat, :lng, :name, NOW(), NOW())
                ON CONFLICT (location_text) DO UPDATE SET last_verified = NOW(), display_name = :name
            """),
            {"key": cache_key, "lat": lat, "lng": lng, "name": display_name or geo_result.get("display_name", "")},
        )
        await db.commit()
    except Exception as e:
        logger.warning(f"Cache write failed: {e}")
        await db.rollback()

    return ReverseGeocodeResponse(
        display_name=display_name or geo_result.get("display_name", f"{lat}, {lng}"),
        locality=geo_result.get("locality", ""),
        suburb=geo_result.get("suburb", ""),
        district=geo_result.get("district", ""),
        city=geo_result.get("city", ""),
        state=geo_result.get("state", ""),
        country=geo_result.get("country", ""),
        latitude=lat,
        longitude=lng,
        cached=False,
        response_time_ms=round(elapsed, 1),
    )
