"""
Geospatial Intelligence Agent

Owns coordinate resolution and deduplication:
  1. Geocode location strings -> lat/lng via Nominatim (with DB cache)
  2. Deduplicate against existing incidents (URL + title similarity + spatial)
  3. Persist verified incidents to PostGIS incidents table
  4. Mark corresponding news_articles as processed
"""

import logging
import time
from typing import List

from sqlalchemy import select, text
from geoalchemy2.elements import WKTElement

from app.database import get_session_factory
from app.models.incident import (
    Incident, IncidentType, IncidentSeverity,
    IncidentSource, IncidentStatus,
)
from app.pipeline.women_safety import (
    WOMEN_SAFETY_TO_INCIDENT_TYPE,
    get_women_safety_details,
    is_women_safety_category,
)
from app.services.nominatim import NominatimService
from app.utils.dedup import (
    title_similarity,
    TITLE_DUP_THRESHOLD,
    TITLE_PROXIMITY_THRESHOLD,
    PROXIMITY_DEG_THRESHOLD,
)
from app.utils.timing import Timer

logger = logging.getLogger(__name__)


class GeospatialIntelligenceAgent:
    name = "geospatial_intelligence"

    async def run(self, incidents: List[dict]) -> dict:
        with Timer("3b. GeospatialIntelligenceAgent.run()"):
            start = time.time()
            logger.info(f"[GEO_AGENT] Processing {len(incidents)} incidents")

        geocoded = await self._geocode(incidents)
        geo_count = sum(1 for i in geocoded if i.get("latitude") is not None)

        save_result = await self._save_incidents(geocoded)

        urls = [i.get("source_url") for i in incidents if i.get("source_url")]
        if urls:
            await self._mark_articles_processed(urls)

        duration = round(time.time() - start, 2)
        logger.info(
            f"[GEO_AGENT] Complete: {geo_count}/{len(incidents)} geocoded, "
            f"{save_result['saved']} saved ({duration}s)"
        )

        return {
            "status": "ok",
            "saved": save_result["saved"],
            "skipped": save_result["skipped"],
            "errors": save_result["errors"],
            "metrics": {
                "geocode": {"geocoded": geo_count, "total": len(incidents)},
                "save": {"saved": save_result["saved"], "skipped": save_result["skipped"]},
                "duration_seconds": duration,
            },
        }

    async def _geocode(self, incidents: List[dict]) -> List[dict]:
        with Timer("10. Geocoding (Nominatim + cache)"):
            nominatim = NominatimService()
            cache_hits = 0
            cache_misses = 0

            factory = get_session_factory()
            async with factory() as session:
                try:
                    for inc in incidents:
                        had_coords = (
                            inc.get("latitude") is not None
                            and inc.get("longitude") is not None
                        )
                        location_str = inc.get("location", "")
                        if not location_str and not had_coords:
                            inc["latitude"] = None
                            inc["longitude"] = None
                            continue

                        query = f"{location_str}, Karnataka, India"
                        try:
                            cached = await session.execute(
                                text("SELECT latitude, longitude, display_name FROM geocoding_cache WHERE location_text = :q"),
                                {"q": query},
                            )
                            row = cached.fetchone()
                            if row:
                                inc["latitude"] = float(row[0])
                                inc["longitude"] = float(row[1])
                                inc["display_name"] = row[2] or ""
                                await session.execute(
                                    text("UPDATE geocoding_cache SET last_verified = NOW() WHERE location_text = :q"),
                                    {"q": query},
                                )
                                cache_hits += 1
                                continue

                            cache_misses += 1
                            named = await nominatim.geocode(query)
                            if named:
                                inc["latitude"] = float(named["lat"])
                                inc["longitude"] = float(named["lng"])
                                inc["display_name"] = named.get("display_name", "")
                                await session.execute(
                                    text("""
                                        INSERT INTO geocoding_cache
                                            (id, location_text, latitude, longitude, display_name, last_verified, created_at)
                                        VALUES (gen_random_uuid(), :q, :lat, :lng, :dn, NOW(), NOW())
                                        ON CONFLICT (location_text) DO NOTHING
                                    """),
                                    {"q": query, "lat": inc["latitude"], "lng": inc["longitude"], "dn": inc.get("display_name", "")},
                                )
                            else:
                                if not had_coords:
                                    inc["latitude"] = None
                                    inc["longitude"] = None

                        except Exception as exc:
                            logger.warning(f"[GEO_AGENT] Geocode error for '{location_str}': {exc}")
                            if not had_coords:
                                inc["latitude"] = None
                                inc["longitude"] = None

                    await session.commit()
                finally:
                    await nominatim.aclose()

            total = cache_hits + cache_misses
            if total > 0:
                logger.info(
                    f"[GEO_AGENT] Geocoding cache: {cache_hits}/{total} hits "
                    f"({cache_hits / total * 100:.1f}%)"
                )
            return incidents

    def _is_duplicate(
        self,
        candidate: dict,
        existing_title: str,
        existing_lat: float,
        existing_lng: float,
    ) -> bool:
        title = (candidate.get("article_title") or candidate.get("title") or "").lower()
        lat = candidate.get("latitude")
        lng = candidate.get("longitude")
        sim = title_similarity(title, existing_title.lower())
        if sim >= TITLE_DUP_THRESHOLD:
            return True
        if sim >= TITLE_PROXIMITY_THRESHOLD and lat and lng:
            dist = ((lat - existing_lat) ** 2 + (lng - existing_lng) ** 2) ** 0.5
            if dist < PROXIMITY_DEG_THRESHOLD:
                return True
        return False

    async def _save_incidents(self, incidents: List[dict]) -> dict:
        with Timer("11b. DB insert - incidents (dedup + persist)"):
            saved = 0
            skipped = 0
            errors: List[str] = []

            factory = get_session_factory()
            async with factory() as session:
                existing_result = await session.execute(
                    select(Incident)
                    .where(Incident.source == IncidentSource.NEWS)
                    .limit(500)
                )
                existing = existing_result.scalars().all()

                for inc in incidents:
                    lat = inc.get("latitude")
                    lng = inc.get("longitude")
                    if lat is None or lng is None:
                        skipped += 1
                        continue

                    source_url = inc.get("source_url", "")
                    if source_url:
                        url_check = await session.execute(
                            select(Incident).where(Incident.source_url == source_url).limit(1)
                        )
                        if url_check.scalar_one_or_none():
                            skipped += 1
                            continue

                    is_dup = any(
                        self._is_duplicate(
                            inc,
                            ex.title or "",
                            ex.latitude or 0.0,
                            ex.longitude or 0.0,
                        )
                        for ex in existing
                    )
                    if is_dup:
                        skipped += 1
                        continue

                    try:
                        incident = self._build_incident(inc, lat, lng)
                        session.add(incident)
                        saved += 1
                    except Exception as exc:
                        logger.error(f"[GEO_AGENT] Failed to build incident: {exc}")
                        errors.append(str(exc))

                await session.commit()

            return {"saved": saved, "skipped": skipped, "errors": errors, "total": len(incidents)}

    @staticmethod
    def _build_incident(inc: dict, lat: float, lng: float) -> Incident:
        from datetime import datetime, timezone

        itype_str = (inc.get("incident_type") or "other").upper()
        try:
            itype = IncidentType(itype_str)
        except ValueError:
            itype = IncidentType.OTHER

        sev_str = (inc.get("severity") or "medium").upper()
        try:
            severity = IncidentSeverity(sev_str)
        except ValueError:
            severity = IncidentSeverity.MEDIUM

        confidence = max(0.0, min(1.0, float(inc.get("confidence", 0.7))))

        ws_cat = inc.get("women_safety_category", "")
        meta: dict = {}
        if ws_cat and is_women_safety_category(ws_cat):
            tier, _risk_weight, sev_weight, _base_sev = get_women_safety_details(ws_cat)
            meta["women_safety_category"] = ws_cat
            meta["women_safety_weight"] = sev_weight
            meta["women_safety_tier"] = tier
            mapped = WOMEN_SAFETY_TO_INCIDENT_TYPE.get(ws_cat)
            if mapped:
                try:
                    itype = IncidentType(mapped)
                except ValueError:
                    pass
            if tier == 1:
                severity = IncidentSeverity.CRITICAL
            elif tier == 2:
                severity = IncidentSeverity.HIGH
        else:
            meta["women_safety_category"] = None
            meta["women_safety_weight"] = None

        return Incident(
            incident_type=itype,
            severity=severity,
            source=IncidentSource.NEWS,
            status=IncidentStatus.PENDING,
            confidence_score=confidence,
            latitude=lat,
            longitude=lng,
            geom=WKTElement(f"POINT({lng} {lat})", srid=4326),
            description=(inc.get("description") or inc.get("article_title", ""))[:500],
            title=(inc.get("article_title", ""))[:500],
            address=inc.get("display_name", ""),
            district=inc.get("district", inc.get("source_city", "")),
            city=inc.get("city", inc.get("source_city", "")),
            incident_date=datetime.now(timezone.utc),
            source_url=inc.get("source_url", ""),
            ai_classified=True,
            meta_data=meta,
        )

    async def _mark_articles_processed(self, urls: List[str]) -> None:
        factory = get_session_factory()
        async with factory() as session:
            try:
                await session.execute(
                    text("UPDATE news_articles SET is_processed = true WHERE url = ANY(:urls)"),
                    {"urls": urls},
                )
                await session.commit()
            except Exception as exc:
                logger.warning(f"[GEO_AGENT] Failed to mark articles processed: {exc}")
