"""
Community Report Pipeline — Simplified.
Processes pending safety_reports: validate, deduplicate, detect spam, save.
"""

import json
import logging
from datetime import datetime, timezone
from typing import List
from sqlalchemy import text

from app.database import get_session_factory
from app.models.incident import (
    Incident, IncidentType, IncidentSeverity,
    IncidentStatus, IncidentSource,
)
from app.services.gemini import gemini_service
from geoalchemy2.elements import WKTElement

logger = logging.getLogger(__name__)

SPAM_THRESHOLD_SECONDS = 30
DUPLICATE_RADIUS_METERS = 100


async def process_pending_reports() -> dict:
    factory = get_session_factory()
    async with factory() as session:
        result = await session.execute(
            text("""
                SELECT id, user_id, incident_type, severity, latitude, longitude,
                       description, confidence_score, created_at
                FROM safety_reports
                WHERE status::text = 'pending'
                ORDER BY created_at ASC
                LIMIT 50
            """)
        )
        rows = result.fetchall()
    if not rows:
        return {"processed": 0, "message": "No pending reports"}
    reports = []
    for r in rows:
        reports.append({
            "id": str(r[0]),
            "user_id": str(r[1]) if r[1] else None,
            "incident_type": r[2],
            "severity": r[3],
            "latitude": float(r[4]) if r[4] else None,
            "longitude": float(r[5]) if r[5] else None,
            "description": r[6] or "",
            "confidence_score": float(r[7]) if r[7] else 0.0,
            "created_at": r[8],
        })
    logger.info(f"Processing {len(reports)} pending reports")
    classified = []
    for report in reports:
        if not gemini_service.is_available():
            report["validated_type"] = report.get("incident_type", "other")
            report["validated_severity"] = report.get("severity", "medium")
            report["confidence_adjustment"] = 0.0
            report["classification_notes"] = "no_ai"
            classified.append(report)
            continue
        prompt = (
            "Validate this community safety report. Return JSON:\n"
            '{"validated_type": "incident_type", "validated_severity": "low|medium|high|critical", '
            '"location_coherent": true/false, "description_valid": true/false, '
            '"confidence_adjustment": -0.3 to 0.3, "notes": "..."}\n\n'
            f"Reported type: {report.get('incident_type', 'unknown')}\n"
            f"Severity: {report.get('severity', 'unknown')}\n"
            f"Location: ({report.get('latitude')}, {report.get('longitude')})\n"
            f"Description: {report.get('description', '')[:500]}"
        )
        try:
            parsed = gemini_service.generate_structured(
                prompt,
                "You are a community report validator. Return ONLY valid JSON.",
            )
            report["validated_type"] = parsed.get("validated_type", report.get("incident_type"))
            report["validated_severity"] = parsed.get("validated_severity", report.get("severity"))
            report["location_coherent"] = parsed.get("location_coherent", True)
            report["description_valid"] = parsed.get("description_valid", True)
            report["confidence_adjustment"] = float(parsed.get("confidence_adjustment", 0.0))
            report["classification_notes"] = parsed.get("notes", "")
        except Exception as e:
            logger.warning(f"Gemini classification failed for report {report.get('id', '?')}: {e}")
            report["validated_type"] = report.get("incident_type", "other")
            report["validated_severity"] = report.get("severity", "medium")
            report["confidence_adjustment"] = 0.0
            report["classification_notes"] = "classification_failed"
        classified.append(report)
    spam_ids = []
    dup_ids = []
    verified_ids = []
    pending_ids = []
    factory = get_session_factory()
    async with factory() as session:
        for report in classified:
            lat = report.get("latitude")
            lng = report.get("longitude")
            is_spam = False
            is_dup = False
            is_dup_of = None
            if lat and lng:
                dup_result = await session.execute(
                    text("""
                        SELECT id FROM incidents
                        WHERE ST_DWithin(
                            geom::geography,
                            ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography,
                            :radius
                        )
                        LIMIT 1
                    """),
                    {"lng": lng, "lat": lat, "radius": DUPLICATE_RADIUS_METERS},
                )
                dup_row = dup_result.fetchone()
                if dup_row:
                    is_dup = True
                    is_dup_of = str(dup_row[0])
            if not report.get("description_valid", True) or not report.get("location_coherent", True):
                is_spam = True
            final_conf = max(0.0, min(1.0, report.get("confidence_score", 0.5) + report.get("confidence_adjustment", 0.0)))
            if is_dup:
                final_status = "duplicate"
                dup_ids.append(report["id"])
            elif is_spam:
                final_status = "spam"
                spam_ids.append(report["id"])
            elif final_conf >= 0.4:
                final_status = "verified"
                verified_ids.append(report["id"])
            else:
                final_status = "pending"
                pending_ids.append(report["id"])
            await session.execute(
                text("""
                    UPDATE safety_reports
                    SET status = :status,
                        incident_type = :itype,
                        severity = :sev,
                        confidence_score = :conf,
                        is_duplicate = :is_dup,
                        duplicate_of = :dup_of,
                        moderated_by = NULL,
                        updated_at = NOW()
                    WHERE id = :rid::uuid
                """),
                {
                    "rid": report["id"],
                    "status": final_status,
                    "itype": report.get("validated_type", report.get("incident_type")),
                    "sev": report.get("validated_severity", report.get("severity")),
                    "conf": final_conf,
                    "is_dup": is_dup,
                    "dup_of": is_dup_of,
                },
            )
            if final_status == "verified" and lat and lng:
                try:
                    itype_str = report.get("validated_type", report.get("incident_type", "other"))
                    sev_str = report.get("validated_severity", report.get("severity", "medium"))
                    try:
                        itype = IncidentType(itype_str)
                    except ValueError:
                        itype = IncidentType.OTHER
                    try:
                        severity = IncidentSeverity(sev_str)
                    except ValueError:
                        severity = IncidentSeverity.MEDIUM
                    incident = Incident(
                        incident_type=itype,
                        severity=severity,
                        source=IncidentSource.COMMUNITY_REPORT,
                        status=IncidentStatus.VERIFIED,
                        confidence_score=final_conf,
                        latitude=lat,
                        longitude=lng,
                        geom=WKTElement(f"POINT({lng} {lat})", srid=4326),
                        description=(report.get("description") or "")[:500],
                        incident_date=datetime.now(timezone.utc),
                        ai_classified=True,
                    )
                    session.add(incident)
                except Exception as e:
                    logger.error(f"Failed to create incident from report {report['id']}: {e}")
        await session.commit()
    return {
        "processed": len(reports),
        "verified": len(verified_ids),
        "duplicates": len(dup_ids),
        "spam": len(spam_ids),
        "pending": len(pending_ids),
    }
