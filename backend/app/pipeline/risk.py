"""
Risk Scoring Engine — Simplified.
Pure math on PostGIS spatial queries. No AI.
"""

import logging
import math
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import text

from app.database import get_session_factory

logger = logging.getLogger(__name__)

HISTORICAL_RADIUS_METERS = 1000
RECENT_RADIUS_METERS = 1000
POLICE_RADIUS_METERS = 2000
HOSPITAL_RADIUS_METERS = 2000
HISTORICAL_RISK_WEIGHT = 0.4
NIGHT_START_HOUR = 21
NIGHT_END_HOUR = 6

DEFAULT_LOCATION_NAME = "Unknown (Pipeline Generated)"


async def ensure_default_location() -> str:
    async with get_session_factory()() as session:
        result = await session.execute(
            text("SELECT id FROM locations LIMIT 1")
        )
        row = result.fetchone()
        if row:
            return str(row[0])
        result = await session.execute(
            text("""
                INSERT INTO locations
                    (id, name, latitude, longitude, metadata, created_at)
                VALUES (gen_random_uuid(), :name, 0.0, 0.0, '{}'::jsonb, NOW())
                RETURNING id
            """),
            {"name": DEFAULT_LOCATION_NAME},
        )
        await session.commit()
        location_id = result.scalar_one()
        logger.info(f"Created default location: {location_id}")
        return str(location_id)


async def score_location(lat: float, lng: float, district: Optional[str] = None) -> dict:
    async with get_session_factory()() as session:
        hist = await session.execute(
            text("""
                SELECT COUNT(*) as cnt,
                       COALESCE(AVG(CASE
                            WHEN UPPER(severity::text) = 'CRITICAL' THEN 50
                            WHEN UPPER(severity::text) = 'HIGH' THEN 30
                            WHEN UPPER(severity::text) = 'MEDIUM' THEN 15
                            WHEN UPPER(severity::text) = 'LOW' THEN 5
                           ELSE 10
                       END), 0) as avg_sev
                FROM incidents
                WHERE ST_DWithin(
                    geom::geography,
                    ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography,
                    :radius
                ) AND status::text != 'dismissed'
            """),
            {"lng": lng, "lat": lat, "radius": HISTORICAL_RADIUS_METERS},
        )
        hrow = hist.fetchone()
        hist_count = int(hrow[0]) if hrow else 0
        hist_sev = float(hrow[1]) if hrow else 0.0

        recent = await session.execute(
            text("""
                SELECT COUNT(*) FROM incidents
                WHERE ST_DWithin(
                    geom::geography,
                    ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography,
                    :radius
                ) AND created_at >= NOW() - INTERVAL '7 days'
                AND status::text != 'dismissed'
            """),
            {"lng": lng, "lat": lat, "radius": RECENT_RADIUS_METERS},
        )
        recent_count = int(recent.scalar() or 0)

        police = await session.execute(
            text("""
                SELECT COUNT(*) FROM police_stations
                WHERE ST_DWithin(
                    geom::geography,
                    ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography,
                    :radius
                )
            """),
            {"lng": lng, "lat": lat, "radius": POLICE_RADIUS_METERS},
        )
        police_count = int(police.scalar() or 0)

        hospitals = await session.execute(
            text("""
                SELECT COUNT(*) FROM hospitals
                WHERE ST_DWithin(
                    geom::geography,
                    ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography,
                    :radius
                )
            """),
            {"lng": lng, "lat": lat, "radius": HOSPITAL_RADIUS_METERS},
        )
        hospital_count = int(hospitals.scalar() or 0)

    # Calculate historical risk
    density_factor = min(1.0, hist_count / 50.0)
    severity_factor = hist_sev / 50.0 if hist_sev > 0 else 0
    historical_risk = (density_factor * 0.6 + severity_factor * 0.4) * 100.0

    # Recent reports impact
    recent_impact = min(30.0, recent_count * 8.0)

    # Night factor
    current_hour = datetime.now(timezone.utc).hour
    is_night = current_hour >= NIGHT_START_HOUR or current_hour < NIGHT_END_HOUR
    night_penalty = 15.0 if is_night else 0.0

    # Safety buffers
    police_bonus = min(10.0, police_count * 3.33)
    hospital_bonus = min(5.0, hospital_count * 1.67)
    safety_bonus = police_bonus + hospital_bonus

    # Severity penalty from recent incidents
    sev_penalty = 0.0
    if recent_count > 0:
        sev_penalty = min(25.0, recent_count * 3.0)

    # Final score
    raw_score = (
        historical_risk * HISTORICAL_RISK_WEIGHT
        + recent_impact * 0.2
        + night_penalty * 0.15
        + sev_penalty * 0.15
        - safety_bonus * 0.1
    )
    score = max(0.0, min(100.0, raw_score))

    if score <= 25:
        category = "SAFE"
    elif score <= 50:
        category = "MODERATE"
    elif score <= 75:
        category = "HIGH_RISK"
    else:
        category = "CRITICAL"

    factors = {
        "historical_risk": round(historical_risk, 2),
        "recent_impact": round(recent_impact, 2),
        "night_penalty": round(night_penalty, 2),
        "severity_penalty": round(sev_penalty, 2),
        "police_presence_bonus": round(police_bonus, 2),
        "hospital_access_bonus": round(hospital_bonus, 2),
        "nearby_police_stations": police_count,
        "nearby_hospitals": hospital_count,
        "is_night": is_night,
    }

    return {"score": round(score, 2), "category": category, "factors": factors}


async def recalculate_all_risk_scores() -> dict:
    location_id = await ensure_default_location()
    async with get_session_factory()() as session:
        result = await session.execute(
            text("SELECT DISTINCT latitude, longitude FROM incidents WHERE latitude IS NOT NULL")
        )
        points = result.fetchall()
    if not points:
        return {"status": "no_data"}
    total = len(points)
    updated = 0
    errors = 0
    for lat, lng in points:
        try:
            result = await score_location(lat, lng)
            async with get_session_factory()() as session:
                try:
                    await session.execute(
                        text("""
                            INSERT INTO risk_scores
                                (id, location_id, latitude, longitude, score, category,
                                 metadata, calculated_at, created_at)
                            VALUES (
                                gen_random_uuid(),
                                COALESCE(
                                    (SELECT id FROM locations ORDER BY created_at LIMIT 1),
                                    gen_random_uuid()
                                ),
                                :lat, :lng, :score, :cat,
                                '{}'::jsonb, NOW(), NOW()
                            )
                            ON CONFLICT (latitude, longitude)
                            DO UPDATE SET
                                score = EXCLUDED.score,
                                category = EXCLUDED.category,
                                calculated_at = NOW()
                        """),
                        {"lat": lat, "lng": lng, "score": result["score"], "cat": result["category"]},
                    )
                    await session.commit()
                    updated += 1
                except Exception as e:
                    await session.rollback()
                    logger.error(f"Risk score failed for ({lat}, {lng}): {e}")
                    errors += 1
        except Exception as e:
            logger.error(f"Risk score failed for ({lat}, {lng}): {e}")
            errors += 1
    return {"total": total, "updated": updated, "errors": errors}
