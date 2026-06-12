import logging
import math
from datetime import datetime, timezone
from typing import List, Tuple
from sqlalchemy import text

from app.database import get_session_factory
from app.pipeline.risk import score_location, ensure_default_location

logger = logging.getLogger(__name__)

GRID_SIZE_DEGREES = 0.009


def _generate_grid(sw_lat: float, sw_lng: float, ne_lat: float, ne_lng: float) -> List[Tuple[float, float]]:
    points = []
    lat = sw_lat
    while lat <= ne_lat:
        lng = sw_lng
        while lng <= ne_lng:
            points.append((round(lat, 6), round(lng, 6)))
            lng += GRID_SIZE_DEGREES
        lat += GRID_SIZE_DEGREES
    return points


async def _score_points_batch(points: List[Tuple[float, float]]) -> List[dict]:
    if not points:
        return []
    radius_m = 1000
    values_clause = ",".join(
        f"({lat},{lng})" for lat, lng in points
    )
    async with get_session_factory()() as session:
        hist = await session.execute(
            text(f"""
                SELECT pt.lat, pt.lng,
                       COUNT(inc.id) as cnt,
                       COALESCE(AVG(CASE
                           WHEN inc.severity::text = 'critical' THEN 50
                           WHEN inc.severity::text = 'high' THEN 30
                           WHEN inc.severity::text = 'medium' THEN 15
                           WHEN inc.severity::text = 'low' THEN 5
                           ELSE 10
                       END), 0) as avg_sev
                FROM (VALUES {values_clause}) AS pt(lat, lng)
                LEFT JOIN incidents inc
                    ON ST_DWithin(
                        inc.geom::geography,
                        ST_SetSRID(ST_MakePoint(pt.lng, pt.lat), 4326)::geography,
                        {radius_m}
                    ) AND inc.status::text != 'dismissed'
                GROUP BY pt.lat, pt.lng
            """)
        )
        hist_rows = {(float(r[0]), float(r[1])): {"cnt": int(r[2]), "sev": float(r[3])} for r in hist.fetchall()}

        recent = await session.execute(
            text(f"""
                SELECT pt.lat, pt.lng, COUNT(inc.id) as cnt
                FROM (VALUES {values_clause}) AS pt(lat, lng)
                LEFT JOIN incidents inc
                    ON ST_DWithin(
                        inc.geom::geography,
                        ST_SetSRID(ST_MakePoint(pt.lng, pt.lat), 4326)::geography,
                        {radius_m}
                    ) AND inc.created_at >= NOW() - INTERVAL '7 days'
                    AND inc.status::text != 'dismissed'
                GROUP BY pt.lat, pt.lng
            """)
        )
        recent_rows = {(float(r[0]), float(r[1])): int(r[2]) for r in recent.fetchall()}

        radius_police = 2000
        radius_hosp = 2000
        police = await session.execute(
            text(f"""
                SELECT pt.lat, pt.lng, COUNT(ps.id) as cnt
                FROM (VALUES {values_clause}) AS pt(lat, lng)
                LEFT JOIN police_stations ps
                    ON ST_DWithin(
                        ps.geom::geography,
                        ST_SetSRID(ST_MakePoint(pt.lng, pt.lat), 4326)::geography,
                        {radius_police}
                    )
                GROUP BY pt.lat, pt.lng
            """)
        )
        police_rows = {(float(r[0]), float(r[1])): int(r[2]) for r in police.fetchall()}

        hospitals = await session.execute(
            text(f"""
                SELECT pt.lat, pt.lng, COUNT(h.id) as cnt
                FROM (VALUES {values_clause}) AS pt(lat, lng)
                LEFT JOIN hospitals h
                    ON ST_DWithin(
                        h.geom::geography,
                        ST_SetSRID(ST_MakePoint(pt.lng, pt.lat), 4326)::geography,
                        {radius_hosp}
                    )
                GROUP BY pt.lat, pt.lng
            """)
        )
        hospital_rows = {(float(r[0]), float(r[1])): int(r[2]) for r in hospitals.fetchall()}

    results = []
    current_hour = datetime.now(timezone.utc).hour
    is_night = current_hour >= 21 or current_hour < 6
    night_penalty = 15.0 if is_night else 0.0

    for lat, lng in points:
        h = hist_rows.get((lat, lng), {"cnt": 0, "sev": 0})
        r_cnt = recent_rows.get((lat, lng), 0)
        p_cnt = police_rows.get((lat, lng), 0)
        h_cnt = hospital_rows.get((lat, lng), 0)

        density_factor = min(1.0, h["cnt"] / 50.0)
        severity_factor = h["sev"] / 50.0 if h["sev"] > 0 else 0
        historical_risk = (density_factor * 0.6 + severity_factor * 0.4) * 100.0
        recent_impact = min(30.0, r_cnt * 8.0)
        sev_penalty = min(25.0, r_cnt * 3.0)
        police_bonus = min(10.0, p_cnt * 3.33)
        hospital_bonus = min(5.0, h_cnt * 1.67)
        safety_bonus = police_bonus + hospital_bonus

        raw_score = (
            historical_risk * 0.4
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

        results.append({
            "latitude": lat,
            "longitude": lng,
            "score": round(score, 2),
            "category": category,
        })
    return results


async def generate_heatmap_for_bounds(
    sw_lat: float, sw_lng: float,
    ne_lat: float, ne_lng: float,
    zoom: str = "city",
) -> dict:
    grid = _generate_grid(sw_lat, sw_lng, ne_lat, ne_lng)
    logger.info(f"Generating heatmap for {len(grid)} grid points")
    all_results = []
    batch_size = 100
    for i in range(0, len(grid), batch_size):
        batch = grid[i:i + batch_size]
        try:
            batch_results = await _score_points_batch(batch)
            all_results.extend(batch_results)
        except Exception as e:
            logger.error(f"Batch heatmap scoring failed at offset {i}: {e}")
            for lat, lng in batch:
                all_results.append({
                    "latitude": lat, "longitude": lng,
                    "score": 50.0, "category": "MODERATE",
                })

    logger.info(f"[HEATMAP_START] Inserting {len(all_results)} heatmap points into risk_scores")
    await ensure_default_location()
    factory = get_session_factory()
    async with factory() as session:
        failures = 0
        MAX_HEATMAP_FAILURES = 10
        for idx, r in enumerate(all_results):
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
                    """),
                    {"lat": r["latitude"], "lng": r["longitude"],
                     "score": r["score"], "cat": r["category"]},
                )
            except Exception as e:
                failures += 1
                logger.error(f"[HEATMAP_POINT_FAILED] ({r['latitude']}, {r['longitude']}): {e}")
                try:
                    await session.rollback()
                    logger.info(f"[HEATMAP_ROLLBACK] Transaction rolled back after failure #{failures}")
                except Exception as rb_e:
                    logger.error(f"[HEATMAP_ROLLBACK] Rollback itself failed: {rb_e}")
                if failures >= MAX_HEATMAP_FAILURES:
                    logger.error(f"[HEATMAP_ABORTED] {failures} consecutive insert failures — aborting")
                    return {
                        "points_generated": idx,
                        "points_failed": len(all_results) - idx,
                        "error": f"HEATMAP_GENERATION_FAILED after {failures} consecutive errors",
                        "bounds": {"sw_lat": sw_lat, "sw_lng": sw_lng, "ne_lat": ne_lat, "ne_lng": ne_lng},
                        "generated_at": datetime.now(timezone.utc).isoformat(),
                    }
        await session.commit()
    logger.info(f"[HEATMAP_COMPLETED] {len(all_results)} heatmap points saved")
    return {
        "points_generated": len(all_results),
        "points_failed": 0,
        "bounds": {"sw_lat": sw_lat, "sw_lng": sw_lng, "ne_lat": ne_lat, "ne_lng": ne_lng},
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


async def get_heatmap_data(
    sw_lat: float, sw_lng: float,
    ne_lat: float, ne_lng: float,
) -> List[dict]:
    factory = get_session_factory()
    async with factory() as session:
        result = await session.execute(
            text("""
                SELECT DISTINCT ON (latitude, longitude)
                    latitude, longitude, score, category
                FROM risk_scores
                WHERE latitude BETWEEN :sw_lat AND :ne_lat
                  AND longitude BETWEEN :sw_lng AND :ne_lng
                  AND calculated_at >= NOW() - INTERVAL '48 hours'
                ORDER BY latitude, longitude, calculated_at DESC
            """),
            {"sw_lat": sw_lat, "ne_lat": ne_lat,
             "sw_lng": sw_lng, "ne_lng": ne_lng},
        )
        rows = result.fetchall()
        return [
            {"latitude": float(r[0]), "longitude": float(r[1]),
             "score": float(r[2]), "category": r[3]}
            for r in rows
        ]