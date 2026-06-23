"""
Community Intelligence Agent

Owns processing of user-submitted safety reports:
  1. Fetch pending safety_reports (LIMIT 50)
  2. Validate each via Gemini (type, severity, women-safety category)
  3. Spam filter (invalid location / bad description)
  4. Spatial deduplication against existing incidents (100m radius)
  5. Promote high-confidence verified reports to incidents table
  6. Update safety_reports.status (PENDING / APPROVED / REJECTED)
"""

import logging
import time
from datetime import datetime, timezone
from typing import List

from sqlalchemy import text
from geoalchemy2.elements import WKTElement

from app.database import get_session_factory
from app.models.incident import (
    Incident, IncidentType, IncidentSeverity,
    IncidentSource, IncidentStatus,
)
from app.pipeline.women_safety import (
    WOMEN_SAFETY_CATEGORIES,
    WOMEN_SAFETY_TO_INCIDENT_TYPE,
    get_women_safety_details,
    is_women_safety_category,
)
from app.services.gemini import gemini_service

logger = logging.getLogger(__name__)

_DUPLICATE_RADIUS_METERS = 100
_CONFIDENCE_THRESHOLD = 0.4
_BATCH_LIMIT = 50

# Pipeline label → DB enum value (UPPERCASE as stored)
_STATUS_MAP = {
    "verified": "APPROVED",
    "duplicate": "REJECTED",
    "spam": "REJECTED",
    "pending": "PENDING",
}


class CommunityIntelligenceAgent:
    """
    Processes pending community safety reports through AI validation and promotion.

    Usage:
        agent = CommunityIntelligenceAgent()
        result = await agent.run()
        # result["processed"]  → int  total reports processed
        # result["verified"]   → int  promoted to incidents
        # result["duplicates"] → int
        # result["spam"]       → int
        # result["metrics"]    → dict
    """

    name = "community_intelligence"

    def __init__(self):
        self._categories_list = sorted(WOMEN_SAFETY_CATEGORIES.keys())

    async def run(self) -> dict:
        start = time.time()
        logger.info("[COMMUNITY_AGENT] Starting community intelligence cycle")

        # Step 1 — fetch pending reports
        reports = await self._fetch_pending()
        if not reports:
            logger.info("[COMMUNITY_AGENT] No pending reports")
            return {
                "status": "ok",
                "processed": 0,
                "verified": 0,
                "duplicates": 0,
                "spam": 0,
                "pending": 0,
                "metrics": {"duration_seconds": round(time.time() - start, 2)},
            }

        # Step 2 — AI classification
        classified = await self._classify(reports)

        # Step 3 — dedup + status resolution + DB writes
        counts = await self._resolve_and_persist(classified)
        duration = round(time.time() - start, 2)

        logger.info(
            f"[COMMUNITY_AGENT] Complete: {len(reports)} processed → "
            f"verified={counts['verified']}, dup={counts['duplicates']}, "
            f"spam={counts['spam']} ({duration}s)"
        )

        return {
            "status": "ok",
            "processed": len(reports),
            **counts,
            "metrics": {"duration_seconds": duration},
        }

    # ──────────────────────────────────────────────────────────────────
    # Step 1: Fetch
    # ──────────────────────────────────────────────────────────────────

    async def _fetch_pending(self) -> List[dict]:
        factory = get_session_factory()
        async with factory() as session:
            result = await session.execute(
                text("""
                    SELECT id, user_id, incident_type, severity, latitude, longitude,
                           description, confidence_score, created_at
                    FROM safety_reports
                    WHERE status = 'PENDING'
                    ORDER BY created_at ASC
                    LIMIT :limit
                """),
                {"limit": _BATCH_LIMIT},
            )
            rows = result.fetchall()

        return [
            {
                "id": str(r[0]),
                "user_id": str(r[1]) if r[1] else None,
                "incident_type": r[2],
                "severity": r[3],
                "latitude": float(r[4]) if r[4] is not None else None,
                "longitude": float(r[5]) if r[5] is not None else None,
                "description": r[6] or "",
                "confidence_score": float(r[7]) if r[7] is not None else 0.0,
                "created_at": r[8],
            }
            for r in rows
        ]

    # ──────────────────────────────────────────────────────────────────
    # Step 2: Gemini validation
    # ──────────────────────────────────────────────────────────────────

    async def _classify(self, reports: List[dict]) -> List[dict]:
        gemini_available = gemini_service.is_available()
        if not gemini_available:
            logger.warning("[COMMUNITY_AGENT] Gemini unavailable — passthrough classification")

        import asyncio
        classified = []
        for report in reports:
            if not gemini_available:
                report.update({
                    "validated_type": report.get("incident_type", "OTHER"),
                    "validated_severity": report.get("severity", "MEDIUM"),
                    "confidence_adjustment": 0.0,
                    "classification_notes": "no_ai",
                    "location_coherent": True,
                    "description_valid": True,
                    "women_safety_category": None,
                })
                classified.append(report)
                continue

            prompt = (
                "Validate this community WOMEN'S SAFETY report. Return JSON:\n"
                '{"validated_type": "incident_type", "validated_severity": "LOW|MEDIUM|HIGH|CRITICAL", '
                '"location_coherent": true/false, "description_valid": true/false, '
                '"women_safety_category": "one of [' + ", ".join(self._categories_list) + '] or null", '
                '"confidence_adjustment": -0.3 to 0.3, "notes": "..."}\n\n'
                "If NOT a women's safety incident, set women_safety_category to null.\n\n"
                f"Reported type: {report.get('incident_type', 'unknown')}\n"
                f"Severity: {report.get('severity', 'unknown')}\n"
                f"Location: ({report.get('latitude')}, {report.get('longitude')})\n"
                f"Description: {report.get('description', '')[:500]}"
            )
            try:
                loop = asyncio.get_event_loop()
                parsed = await loop.run_in_executor(
                    None,
                    lambda p=prompt: gemini_service.generate_structured(
                        p,
                        "You are a community report validator. Return ONLY valid JSON.",
                    ),
                )
                report["validated_type"] = parsed.get("validated_type", report.get("incident_type"))
                report["validated_severity"] = parsed.get("validated_severity", report.get("severity"))
                report["location_coherent"] = parsed.get("location_coherent", True)
                report["description_valid"] = parsed.get("description_valid", True)
                report["confidence_adjustment"] = float(parsed.get("confidence_adjustment", 0.0))
                report["classification_notes"] = parsed.get("notes", "")
                report["women_safety_category"] = parsed.get("women_safety_category")
            except Exception as exc:
                logger.warning(f"[COMMUNITY_AGENT] Gemini failed for report {report.get('id')}: {exc}")
                report.update({
                    "validated_type": report.get("incident_type", "OTHER"),
                    "validated_severity": report.get("severity", "MEDIUM"),
                    "confidence_adjustment": 0.0,
                    "classification_notes": "classification_failed",
                    "location_coherent": True,
                    "description_valid": True,
                    "women_safety_category": None,
                })
            classified.append(report)

        return classified

    # ──────────────────────────────────────────────────────────────────
    # Step 3: Resolve + persist
    # ──────────────────────────────────────────────────────────────────

    async def _resolve_and_persist(self, classified: List[dict]) -> dict:
        verified = 0
        duplicates = 0
        spam = 0
        pending = 0

        factory = get_session_factory()
        async with factory() as session:
            for report in classified:
                lat = report.get("latitude")
                lng = report.get("longitude")

                # Spatial duplicate check
                is_dup = False
                if lat is not None and lng is not None:
                    try:
                        dup = await session.execute(
                            text("""
                                SELECT id FROM incidents
                                WHERE ST_DWithin(
                                    geom::geography,
                                    ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography,
                                    :radius
                                )
                                LIMIT 1
                            """),
                            {"lng": lng, "lat": lat, "radius": _DUPLICATE_RADIUS_METERS},
                        )
                        if dup.fetchone():
                            is_dup = True
                    except Exception as exc:
                        logger.warning(f"[COMMUNITY_AGENT] Dedup check failed: {exc}")

                is_spam = (
                    not report.get("description_valid", True)
                    or not report.get("location_coherent", True)
                )
                final_conf = max(
                    0.0,
                    min(1.0, report.get("confidence_score", 0.5) + report.get("confidence_adjustment", 0.0)),
                )

                if is_dup:
                    pipeline_status = "duplicate"
                    duplicates += 1
                elif is_spam:
                    pipeline_status = "spam"
                    spam += 1
                elif final_conf >= _CONFIDENCE_THRESHOLD:
                    pipeline_status = "verified"
                    verified += 1
                else:
                    pipeline_status = "pending"
                    pending += 1

                db_status = _STATUS_MAP.get(pipeline_status, "PENDING")

                try:
                    await session.execute(
                        text("""
                            UPDATE safety_reports
                            SET status = :status,
                                confidence_score = :conf,
                                moderated_by = NULL,
                                updated_at = NOW()
                            WHERE id = :rid
                        """),
                        {"rid": report["id"], "status": db_status, "conf": final_conf},
                    )
                except Exception as exc:
                    logger.error(f"[COMMUNITY_AGENT] Failed to update report {report['id']}: {exc}")
                    await session.rollback()
                    continue

                # Promote verified reports to incidents
                if pipeline_status == "verified" and lat is not None and lng is not None:
                    try:
                        incident = self._build_incident(report, lat, lng, final_conf)
                        session.add(incident)
                    except Exception as exc:
                        logger.error(f"[COMMUNITY_AGENT] Failed to create incident: {exc}")

            await session.commit()

        return {
            "verified": verified,
            "duplicates": duplicates,
            "spam": spam,
            "pending": pending,
        }

    @staticmethod
    def _build_incident(report: dict, lat: float, lng: float, confidence: float) -> Incident:
        itype_str = (report.get("validated_type") or report.get("incident_type") or "OTHER").upper()
        sev_str = (report.get("validated_severity") or report.get("severity") or "MEDIUM").upper()

        try:
            itype = IncidentType(itype_str)
        except ValueError:
            itype = IncidentType.OTHER

        try:
            severity = IncidentSeverity(sev_str)
        except ValueError:
            severity = IncidentSeverity.MEDIUM

        ws_cat = report.get("women_safety_category", "")
        meta: dict = {}
        if ws_cat and is_women_safety_category(ws_cat):
            tier, _rw, sev_weight, _bs = get_women_safety_details(ws_cat)
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
            source=IncidentSource.COMMUNITY_REPORT,
            status=IncidentStatus.VERIFIED,
            confidence_score=confidence,
            latitude=lat,
            longitude=lng,
            geom=WKTElement(f"POINT({lng} {lat})", srid=4326),
            description=(report.get("description") or "")[:500],
            incident_date=datetime.now(timezone.utc),
            ai_classified=True,
            meta_data=meta,
        )
