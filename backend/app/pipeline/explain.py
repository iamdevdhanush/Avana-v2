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

    async with factory() as session:
        # 1. Score + trend from risk_scores
        score_row = await session.execute(
            text("""
                SELECT score, category, calculated_at
                FROM risk_scores
                WHERE latitude BETWEEN :lat - 0.01 AND :lat + 0.01
                  AND longitude BETWEEN :lng - 0.01 AND :lng + 0.01
                ORDER BY calculated_at DESC
                LIMIT 1
            """),
            {"lat": lat, "lng": lng},
        )
        score_data = score_row.fetchone()

        risk_score = float(score_data[0]) if score_data else 50.0
        risk_category = str(score_data[1]) if score_data else "MODERATE"
        last_calculated = score_data[2] if score_data else datetime.now(timezone.utc)

        # 2. Trend from recent risk_scores history
        trend_row = await session.execute(
            text("""
                SELECT calculated_at, score
                FROM risk_scores
                WHERE latitude BETWEEN :lat - 0.01 AND :lat + 0.01
                  AND longitude BETWEEN :lng - 0.01 AND :lng + 0.01
                ORDER BY calculated_at DESC
                LIMIT 2
            """),
            {"lat": lat, "lng": lng},
        )
        trend_data = trend_row.fetchall()
        if len(trend_data) >= 2:
            diff = float(trend_data[0][1]) - float(trend_data[1][1])
            trend = "worsening" if diff > 5 else ("improving" if diff < -5 else "stable")
        else:
            trend = "stable"

        # 3. Incident breakdown by source within radius
        inc_rows = await session.execute(
            text("""
                SELECT source, COUNT(*) as cnt
                FROM incidents
                WHERE ST_DWithin(
                    geom::geography,
                    ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography,
                    :radius_m
                )
                  AND status::text != 'dismissed'
                GROUP BY source
            """),
            {"lat": lat, "lng": lng, "radius_m": radius_m},
        )
        source_counts: dict = {}
        for r in inc_rows.fetchall():
            source_counts[str(r[0]).upper()] = int(r[1])

        # 4. Detailed incidents list
        detail_rows = await session.execute(
            text("""
                SELECT id, incident_type, severity, source, created_at,
                       title, description, source_url, metadata,
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
                  AND status::text != 'dismissed'
                ORDER BY dist ASC
                LIMIT 25
            """),
            {"lat": lat, "lng": lng, "radius_m": radius_m},
        )
        raw_rows = detail_rows.fetchall()

        # 5. Police datasets count (crime_stats near location)
        police_ds = await session.execute(
            text("""
                SELECT COUNT(*) FROM crime_stats
                WHERE latitude IS NOT NULL
                  AND ST_DWithin(
                      geom::geography,
                      ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography,
                      :radius_m
                  )
            """),
            {"lat": lat, "lng": lng, "radius_m": radius_m},
        )
        police_ds_count = police_ds.scalar() or 0

    # ── Build response ──────────────────────────────────────────────────────
    police_cnt = source_counts.get("POLICE", 0)
    verified_cnt = source_counts.get("USER_REPORT", 0) + source_counts.get("SYSTEM", 0)
    community_cnt = source_counts.get("COMMUNITY_REPORT", 0)
    news_cnt = source_counts.get("NEWS", 0)

    why_score = {
        "police_crime_data": police_cnt + police_ds_count,
        "verified_incidents": verified_cnt,
        "community_reports": community_cnt,
        "news_intelligence": news_cnt,
    }

    total_data_points = sum(why_score.values())
    if total_data_points >= 20:
        confidence_score = round(90 + min(10, total_data_points * 0.3), 0)
    elif total_data_points >= 10:
        confidence_score = 75.0
    elif total_data_points >= 5:
        confidence_score = 60.0
    elif total_data_points >= 2:
        confidence_score = 40.0
    else:
        confidence_score = 20.0

    confidence = {
        "score": min(99, confidence_score),
        "based_on": [
            f"{v} {'verified incidents' if k == 'verified_incidents' else k.replace('_', ' ')}"
            for k, v in sorted(why_score.items(), key=lambda x: -x[1])
            if v > 0
        ],
    }

    level_map = {
        "SAFE": "Low",
        "MODERATE": "Moderate",
        "HIGH_RISK": "Elevated",
        "CRITICAL": "High",
    }

    contributing_incidents: List[dict] = []
    for r in raw_rows:
        inc_id = str(r[0])
        inc_type = str(r[1])
        severity = str(r[2])
        inc_source = str(r[3])
        created = r[4]
        title = str(r[5]) if r[5] else None
        description = str(r[6]) if r[6] else None
        source_url = str(r[7]) if r[7] else None
        raw_meta = r[8] if r[8] else {}
        dist_m = float(r[9]) if r[9] else 0.0

        item: dict = {
            "id": inc_id,
            "incident_type": inc_type,
            "severity": severity,
            "date": created.isoformat() if hasattr(created, "isoformat") else str(created),
            "distance_km": round(dist_m / 1000, 2),
            "source": inc_source,
            "title": title,
            "description": description,
            "source_url": source_url,
            "news_metadata": None,
            "police_metadata": None,
        }

        if inc_source.upper() == "NEWS" and source_url:
            meta = raw_meta if isinstance(raw_meta, dict) else {}
            item["news_metadata"] = {
                "title": title or "News Article",
                "publisher": meta.get("publisher", meta.get("source_name", "News Source")),
                "published_at": created.isoformat() if hasattr(created, "isoformat") else str(created),
                "url": source_url,
            }

        if inc_source.upper() == "POLICE":
            meta = raw_meta if isinstance(raw_meta, dict) else {}
            item["police_metadata"] = {
                "dataset_name": meta.get("source_name", meta.get("dataset_name", "Karnataka Police Dataset")),
                "reporting_year": meta.get("year", datetime.now(timezone.utc).year),
                "district": meta.get("district", "Unknown"),
                "crime_category": meta.get("crime_category", inc_type),
            }

        contributing_incidents.append(item)

    # Source attributions
    sources: List[dict] = []
    if police_cnt > 0 or police_ds_count > 0:
        items = []
        if police_ds_count > 0:
            items.append({"name": "Karnataka Police Open Data", "detail": f"{police_ds_count} dataset records", "count": police_ds_count})
        if police_cnt > 0:
            items.append({"name": "Police Reports", "detail": f"{police_cnt} verified police incident records", "count": police_cnt})
        sources.append({"type": "police_dataset", "label": "Police Data", "count": police_cnt + police_ds_count, "items": items})
    if verified_cnt > 0:
        sources.append({"type": "verified_incident", "label": "Verified Incidents", "count": verified_cnt, "items": [{"name": "User Reports", "detail": f"{verified_cnt} verified user reports", "count": verified_cnt}]})
    if community_cnt > 0:
        sources.append({"type": "community_report", "label": "Community Reports", "count": community_cnt, "items": [{"name": "Community Safety Reports", "detail": f"{community_cnt} community reports", "count": community_cnt}]})
    if news_cnt > 0:
        news_items = []
        news_urls_seen = set()
        for inc in contributing_incidents:
            if inc["source"].upper() == "NEWS" and inc["source_url"] and inc["source_url"] not in news_urls_seen:
                news_urls_seen.add(inc["source_url"])
                news_items.append({
                    "name": inc.get("news_metadata", {}).get("publisher", "News Source"),
                    "detail": inc.get("title", "News Article")[:120],
                    "count": 1,
                })
        sources.append({"type": "news_article", "label": "News Intelligence", "count": news_cnt, "items": news_items[:10]})

    return {
        "score": risk_score,
        "level": level_map.get(risk_category, "Moderate"),
        "trend": trend,
        "last_updated": last_calculated.isoformat() if hasattr(last_calculated, "isoformat") else str(last_calculated),
        "why_score": why_score,
        "contributing_incidents": contributing_incidents,
        "sources": sources,
        "confidence": confidence,
    }
