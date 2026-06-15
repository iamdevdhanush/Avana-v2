import logging
from datetime import datetime, timezone
from typing import List

from sqlalchemy import text

from app.database import get_session_factory

logger = logging.getLogger(__name__)


async def explain_risk(
    lat: float,
    lng: float,
    radius_km: float = 1.0,
) -> dict:
    radius_m = int(radius_km * 1000)
    factory = get_session_factory()

    risk_score = 50.0
    risk_category = "Moderate"
    incident_count = 0
    sources: List[dict] = []

    try:
        async with factory() as session:
            # 1. Score from risk_scores
            try:
                sr = await session.execute(
                    text("""
                        SELECT score, category
                        FROM risk_scores
                        WHERE latitude BETWEEN :lat - 0.01 AND :lat + 0.01
                          AND longitude BETWEEN :lng - 0.01 AND :lng + 0.01
                        ORDER BY calculated_at DESC
                        LIMIT 1
                    """),
                    {"lat": lat, "lng": lng},
                )
                row = sr.fetchone()
                if row:
                    risk_score = float(row[0])
                    risk_category = str(row[1])
            except Exception as e:
                logger.warning(f"[EXPLAIN] risk_scores query failed: {e}")

            # 2. Incidents within radius
            try:
                ir = await session.execute(
                    text("""
                        SELECT id, incident_type, severity, created_at,
                               title, source, source_url, metadata,
                               ST_Distance(
                                   geom::geography,
                                   ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography
                               ) as dist
                        FROM incidents
                        WHERE ST_DWithin(
                            geom::geography,
                            ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography,
                            :radius_m
                        )
                          AND (status IS NULL OR status::text != 'dismissed')
                        ORDER BY dist ASC
                        LIMIT 25
                    """),
                    {"lat": lat, "lng": lng, "radius_m": radius_m},
                )
                for r in ir.fetchall():
                    dist_m = float(r[8]) if r[8] else 0.0
                    raw_source = str(r[5])
                    raw_meta = r[7] if r[7] else {}
                    if not isinstance(raw_meta, dict):
                        raw_meta = {}

                    women_safety_cat = raw_meta.get("women_safety_category") if isinstance(raw_meta, dict) else None

                    item: dict = {
                        "title": str(r[4]) if r[4] else None,
                        "incident_type": str(r[1]),
                        "severity": str(r[2]),
                        "date": r[3].isoformat() if hasattr(r[3], "isoformat") else str(r[3]),
                        "source": raw_source,
                        "source_url": str(r[6]) if r[6] else None,
                        "distance_meters": round(dist_m, 1),
                        "publisher": None,
                        "dataset_name": None,
                        "dataset_year": None,
                        "dataset_district": None,
                        "women_safety_category": women_safety_cat,
                    }

                    if raw_source.upper() == "NEWS":
                        item["publisher"] = raw_meta.get("publisher") or raw_meta.get("source_name") or "News Source"

                    sources.append(item)
                    incident_count += 1
            except Exception as e:
                logger.warning(f"[EXPLAIN] incidents query failed: {e}")

            # 3. Crime stats nearby — NO geom column, inline ST_MakePoint
            try:
                cs = await session.execute(
                    text("""
                        SELECT COUNT(*)
                        FROM crime_stats
                        WHERE latitude IS NOT NULL
                          AND longitude IS NOT NULL
                          AND ST_DWithin(
                              ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)::geography,
                              ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography,
                              :radius_m
                          )
                    """),
                    {"lat": lat, "lng": lng, "radius_m": radius_m},
                )
                cs_count = cs.scalar() or 0
                incident_count += cs_count

                if cs_count > 0:
                    csd = await session.execute(
                        text("""
                            SELECT crime_type, crime_category, year,
                                   crime_count, district, source_name
                            FROM crime_stats
                            WHERE latitude IS NOT NULL
                              AND longitude IS NOT NULL
                              AND ST_DWithin(
                                  ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)::geography,
                                  ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography,
                                  :radius_m
                              )
                            ORDER BY year DESC
                            LIMIT 10
                        """),
                        {"lat": lat, "lng": lng, "radius_m": radius_m},
                    )
                    for r in csd.fetchall():
                        crime_type = str(r[0])
                        crime_cat = str(r[1]) if r[1] else None
                        year_val = int(r[2]) if r[2] else datetime.now(timezone.utc).year
                        crime_cnt = int(r[3]) if r[3] else 0
                        district_name = str(r[4]) if r[4] else "Unknown"
                        ds_name = str(r[5]) if r[5] else "Karnataka Police Dataset"

                        label = f"{crime_type} ({crime_cat})" if crime_cat else crime_type
                        sources.append({
                            "title": f"Police Record: {label}",
                            "incident_type": crime_cat or crime_type,
                            "severity": "HIGH" if crime_cnt > 10 else "MEDIUM" if crime_cnt > 3 else "LOW",
                            "date": str(year_val),
                            "source": "POLICE",
                            "source_url": None,
                            "distance_meters": 0,
                            "publisher": None,
                            "dataset_name": ds_name,
                            "dataset_year": year_val,
                            "dataset_district": district_name,
                        })
            except Exception as e:
                logger.warning(f"[EXPLAIN] crime_stats query failed: {e}")

    except Exception as e:
        logger.exception(f"[EXPLAIN] Unexpected error: {e}")

    cat_map = {
        "SAFE": "Low", "MODERATE": "Moderate",
        "HIGH_RISK": "Elevated", "CRITICAL": "High",
        "Low": "Low", "Moderate": "Moderate",
        "High Risk": "Elevated", "High": "High", "Critical": "High",
    }
    level = cat_map.get(risk_category, "Moderate")

    return {
        "risk_score": round(risk_score, 1),
        "risk_category": level,
        "incident_count": incident_count,
        "sources": sources,
    }
