import logging
import math
from datetime import datetime, timezone
from typing import List, Tuple
from sqlalchemy import text

from app.database import get_session_factory
from app.pipeline.risk import score_location, _check_data_sufficiency, _count_crime_stats_nearby

logger = logging.getLogger(__name__)

GRID_SIZE_DEGREES = 0.009
MAX_GRID_CELLS = 50_000


def _estimate_grid_cells(sw_lat: float, sw_lng: float, ne_lat: float, ne_lng: float) -> int:
    lat_cells = max(1, math.ceil((ne_lat - sw_lat) / GRID_SIZE_DEGREES))
    lng_cells = max(1, math.ceil((ne_lng - sw_lng) / GRID_SIZE_DEGREES))
    return lat_cells * lng_cells


def _split_bounds(
    sw_lat: float, sw_lng: float, ne_lat: float, ne_lng: float,
) -> List[Tuple[float, float, float, float]]:
    cells = _estimate_grid_cells(sw_lat, sw_lng, ne_lat, ne_lng)
    if cells <= MAX_GRID_CELLS:
        return [(sw_lat, sw_lng, ne_lat, ne_lng)]
    ratio = math.ceil(math.sqrt(cells / MAX_GRID_CELLS))
    lat_step = (ne_lat - sw_lat) / ratio
    lng_step = (ne_lng - sw_lng) / ratio
    chunks = []
    for i in range(ratio):
        for j in range(ratio):
            c_sw_lat = sw_lat + i * lat_step
            c_ne_lat = sw_lat + (i + 1) * lat_step if i < ratio - 1 else ne_lat
            c_sw_lng = sw_lng + j * lng_step
            c_ne_lng = sw_lng + (j + 1) * lng_step if j < ratio - 1 else ne_lng
            chunk_cells = _estimate_grid_cells(c_sw_lat, c_sw_lng, c_ne_lat, c_ne_lng)
            if chunk_cells == 0:
                continue
            if chunk_cells > MAX_GRID_CELLS:
                chunks.extend(_split_bounds(c_sw_lat, c_sw_lng, c_ne_lat, c_ne_lng))
            else:
                chunks.append((c_sw_lat, c_sw_lng, c_ne_lat, c_ne_lng))
    return chunks


async def compute_localized_bounds(buffer_degrees: float = 0.05, max_cells_per: int = 1000) -> List[Tuple[float, float, float, float]]:
    bounds_list: List[Tuple[float, float, float, float]] = []
    async with get_session_factory()() as session:
        result = await session.execute(
            text("""
                SELECT district,
                       MIN(latitude) as min_lat, MAX(latitude) as max_lat,
                       MIN(longitude) as min_lng, MAX(longitude) as max_lng
                FROM incidents
                WHERE latitude IS NOT NULL
                  AND metadata->>'women_safety_category' IS NOT NULL
                  AND status::text IN ('verified', 'VERIFIED')
                  AND created_at >= NOW() - INTERVAL '7 days'
                GROUP BY district
            """)
        )
        rows = result.fetchall()
        for row in rows:
            sw_lat = row[1] - buffer_degrees
            ne_lat = row[2] + buffer_degrees
            sw_lng = row[3] - buffer_degrees
            ne_lng = row[4] + buffer_degrees
            cells = _estimate_grid_cells(sw_lat, sw_lng, ne_lat, ne_lng)
            if cells <= max_cells_per:
                bounds_list.append((sw_lat, sw_lng, ne_lat, ne_lng))
            else:
                logger.warning(f"[HEATMAP] District '{row[0]}' exceeds {max_cells_per} cells ({cells}) — skipping")
    return bounds_list


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
                       COALESCE(AVG(
                           COALESCE(
                               (inc.metadata->>'women_safety_weight')::float,
                               CASE
                                   WHEN UPPER(inc.severity::text) = 'CRITICAL' THEN 100
                                   WHEN UPPER(inc.severity::text) = 'HIGH' THEN 70
                                   WHEN UPPER(inc.severity::text) = 'MEDIUM' THEN 40
                                   WHEN UPPER(inc.severity::text) = 'LOW' THEN 20
                                   ELSE 10
                               END
                           )
                       ), 0) as avg_wt
                FROM (VALUES {values_clause}) AS pt(lat, lng)
                LEFT JOIN incidents inc
                    ON ST_DWithin(
                        inc.geom::geography,
                        ST_SetSRID(ST_MakePoint(pt.lng, pt.lat), 4326)::geography,
                        {radius_m}
                    )
                    AND inc.metadata->>'women_safety_category' IS NOT NULL
                    AND inc.status::text IN ('verified', 'VERIFIED')
                GROUP BY pt.lat, pt.lng
            """)
        )
        hist_rows = {(float(r[0]), float(r[1])): {"cnt": int(r[2]), "wt": float(r[3])} for r in hist.fetchall()}

        recent = await session.execute(
            text(f"""
                SELECT pt.lat, pt.lng, COUNT(inc.id) as cnt,
                       COALESCE(AVG(
                           COALESCE(
                               (inc.metadata->>'women_safety_weight')::float, 40.0
                           ) * CASE
                               WHEN inc.created_at >= NOW() - INTERVAL '30 days' THEN 1.0
                               WHEN inc.created_at >= NOW() - INTERVAL '90 days' THEN 0.8
                               WHEN inc.created_at >= NOW() - INTERVAL '180 days' THEN 0.6
                               ELSE 0.4
                           END
                       ), 0) as weighted_impact
                FROM (VALUES {values_clause}) AS pt(lat, lng)
                LEFT JOIN incidents inc
                    ON ST_DWithin(
                        inc.geom::geography,
                        ST_SetSRID(ST_MakePoint(pt.lng, pt.lat), 4326)::geography,
                        {radius_m}
                    )
                    AND inc.created_at >= NOW() - INTERVAL '30 days'
                    AND inc.metadata->>'women_safety_category' IS NOT NULL
                    AND inc.status::text IN ('verified', 'VERIFIED')
                GROUP BY pt.lat, pt.lng
            """)
        )
        recent_rows = {(float(r[0]), float(r[1])): {"cnt": int(r[2]), "weighted_impact": float(r[3])} for r in recent.fetchall()}

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

        all_counts = await session.execute(
            text(f"""
                SELECT pt.lat, pt.lng, COUNT(inc.id) as cnt
                FROM (VALUES {values_clause}) AS pt(lat, lng)
                LEFT JOIN incidents inc
                    ON ST_DWithin(
                        inc.geom::geography,
                        ST_SetSRID(ST_MakePoint(pt.lng, pt.lat), 4326)::geography,
                        {radius_m}
                    )
                    AND inc.status::text IN ('verified', 'VERIFIED')
                GROUP BY pt.lat, pt.lng
            """)
        )
        all_inc_rows = {(float(r[0]), float(r[1])): int(r[2]) for r in all_counts.fetchall()}

        crime_rows = {}
        try:
            cr = await session.execute(
                text(f"""
                    SELECT pt.lat, pt.lng, COUNT(*) as cnt
                    FROM (VALUES {values_clause}) AS pt(lat, lng)
                    LEFT JOIN crime_stats cs
                        ON cs.latitude IS NOT NULL
                        AND cs.longitude IS NOT NULL
                        AND ST_DWithin(
                            ST_SetSRID(ST_MakePoint(cs.longitude, cs.latitude), 4326)::geography,
                            ST_SetSRID(ST_MakePoint(pt.lng, pt.lat), 4326)::geography,
                            {radius_m * 2}
                        )
                    GROUP BY pt.lat, pt.lng
                """)
            )
            for r in cr.fetchall():
                crime_rows[(float(r[0]), float(r[1]))] = int(r[2])
        except Exception:
            pass

    results = []
    current_hour = datetime.now(timezone.utc).hour
    is_night = current_hour >= 21 or current_hour < 6
    night_score = 10.0 if is_night else 0.0

    for lat, lng in points:
        h = hist_rows.get((lat, lng), {"cnt": 0, "wt": 0})
        r = recent_rows.get((lat, lng), {"cnt": 0, "weighted_impact": 0})
        r_cnt = r["cnt"]
        r_weighted = r["weighted_impact"]
        p_cnt = police_rows.get((lat, lng), 0)
        h_cnt = hospital_rows.get((lat, lng), 0)
        all_cnt = all_inc_rows.get((lat, lng), 0)
        crime_cnt = crime_rows.get((lat, lng), 0)

        # Data sufficiency check
        sufficient, _ = _check_data_sufficiency(h["cnt"], r_cnt, crime_cnt)

        if not sufficient:
            results.append({
                "latitude": lat,
                "longitude": lng,
                "score": 0.0,
                "category": "UNKNOWN",
            })
            continue

        # v2 Risk Formula
        density_log = math.log10(h["cnt"] + 1) / math.log10(51) if h["cnt"] > 0 else 0.0
        density_score = min(50.0, density_log * 50.0)

        if h["wt"] > 0:
            severity_score = (h["wt"] / 100.0) * 25.0
        else:
            severity_score = 0.0

        if r_cnt > 0:
            recency_raw = min(15.0, (r_weighted / 100.0) * 15.0)
            recency_count_bonus = min(5.0, r_cnt * 1.5)
            recency_score = min(15.0, recency_raw + recency_count_bonus * 0.3)
        else:
            recency_score = 0.0

        police_bonus = min(15.0, p_cnt * 5.0)
        hospital_bonus = min(5.0, h_cnt * 2.5)
        safety_reduction = min(20.0, police_bonus + hospital_bonus)

        raw_before_buffer = density_score + severity_score + recency_score + night_score
        if raw_before_buffer > 0:
            reduction_ratio = min(1.0, safety_reduction / max(1.0, raw_before_buffer))
            final_score = raw_before_buffer * (1.0 - reduction_ratio * 0.3)
        else:
            final_score = 0.0

        score = max(0.0, min(100.0, final_score))

        if score <= 20:
            category = "SAFE"
        elif score <= 40:
            category = "MODERATE"
        elif score <= 65:
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
    estimated = _estimate_grid_cells(sw_lat, sw_lng, ne_lat, ne_lng)
    lat_cells = max(1, math.ceil((ne_lat - sw_lat) / GRID_SIZE_DEGREES))
    lng_cells = max(1, math.ceil((ne_lng - sw_lng) / GRID_SIZE_DEGREES))
    logger.info(f"[HEATMAP] Estimated grid cells: {estimated} ({lat_cells}×{lng_cells})")
    logger.info(f"[HEATMAP] Bounds: sw=({sw_lat:.4f},{sw_lng:.4f}) ne=({ne_lat:.4f},{ne_lng:.4f})")

    if estimated > MAX_GRID_CELLS:
        chunks = _split_bounds(sw_lat, sw_lng, ne_lat, ne_lng)
        logger.warning(f"[HEATMAP] Bounds exceed MAX_GRID_CELLS ({estimated} > {MAX_GRID_CELLS}) — splitting into {len(chunks)} chunks")
        total_points = 0
        chunk_errors = []
        for i, (c_sw_lat, c_sw_lng, c_ne_lat, c_ne_lng) in enumerate(chunks):
            logger.info(f"[HEATMAP] Chunk {i+1}/{len(chunks)}: ({c_sw_lat:.4f},{c_sw_lng:.4f}) to ({c_ne_lat:.4f},{c_ne_lng:.4f})")
            chunk_result = await generate_heatmap_for_bounds(c_sw_lat, c_sw_lng, c_ne_lat, c_ne_lng, zoom)
            if "error" in chunk_result:
                chunk_errors.append(chunk_result["error"])
            total_points += chunk_result.get("points_generated", 0)
        result = {"points_generated": total_points, "chunks_used": len(chunks)}
        if chunk_errors:
            result["error"] = "; ".join(chunk_errors)
        return result

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
                    "score": 0.0, "category": "UNKNOWN",
                })

    logger.info(f"[HEATMAP_START] Inserting {len(all_results)} heatmap points into risk_scores")
    from app.pipeline.risk import ensure_default_location
    loc_id = await ensure_default_location()
    factory = get_session_factory()
    async with factory() as session:
        failures = 0
        MAX_HEATMAP_FAILURES = 10
        for idx, r in enumerate(all_results):
            try:
                async with session.begin_nested():
                    await session.execute(
                        text("""
                            INSERT INTO risk_scores
                                (id, location_id, latitude, longitude, score, category,
                                 metadata, calculated_at, created_at)
                            VALUES (
                                gen_random_uuid(),
                                :location_id, :lat, :lng, :score, :cat,
                                '{}'::jsonb, NOW(), NOW()
                            )
                            ON CONFLICT (latitude, longitude)
                            DO UPDATE SET
                                score = :score,
                                category = :cat,
                                calculated_at = NOW()
                        """),
                        {"lat": r["latitude"], "lng": r["longitude"],
                         "score": r["score"], "cat": r["category"],
                         "location_id": loc_id},
                    )
            except Exception as e:
                failures += 1
                logger.error(f"[HEATMAP_POINT_FAILED] ({r['latitude']}, {r['longitude']}): {e}")
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
    min_score: float = 0,
) -> List[dict]:
    factory = get_session_factory()
    async with factory() as session:
        total_risk = await session.execute(text("SELECT COUNT(*) FROM risk_scores"))
        total_count = total_risk.scalar() or 0
        logger.info(f"[HEATMAP] Total risk_scores in DB: {total_count}")

        result = await session.execute(
            text("""
                SELECT DISTINCT ON (latitude, longitude)
                    latitude, longitude, score, category
                FROM risk_scores
                WHERE latitude BETWEEN :sw_lat AND :ne_lat
                  AND longitude BETWEEN :sw_lng AND :ne_lng
                ORDER BY latitude, longitude, calculated_at DESC
            """),
            {"sw_lat": sw_lat, "ne_lat": ne_lat,
             "sw_lng": sw_lng, "ne_lng": ne_lng},
        )
        rows = result.fetchall()
        logger.info(f"[HEATMAP] points returned: {len(rows)} (bounds: {sw_lat:.4f}-{ne_lat:.4f}, {sw_lng:.4f}-{ne_lng:.4f})")

        risk_all_bounds = await session.execute(
            text("""
                SELECT COUNT(*) FROM risk_scores
                WHERE latitude BETWEEN :sw_lat AND :ne_lat
                  AND longitude BETWEEN :sw_lng AND :ne_lng
            """),
            {"sw_lat": sw_lat, "ne_lat": ne_lat,
             "sw_lng": sw_lng, "ne_lng": ne_lng},
        )
        bounds_count = risk_all_bounds.scalar() or 0
        logger.info(f"[HEATMAP] risk scores in bounds (any age): {bounds_count}")

        return [
            {"latitude": float(r[0]), "longitude": float(r[1]),
             "score": float(r[2]), "category": r[3]}
            for r in rows
        ]
