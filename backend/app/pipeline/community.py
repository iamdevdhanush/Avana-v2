"""
Community Report Pipeline — Fixed.

Root causes addressed:
1. `status::text = 'pending'` used for SELECT (works), but UPDATE used lowercase
   'pending'/'verified'/etc. which are INVALID for the DB enum (PENDING, APPROVED, REJECTED).
2. UPDATE referenced `is_duplicate` and `duplicate_of` columns that DO NOT EXIST
   in the `safety_reports` table — only `incidents` has them.
3. Added per-stage debug logging throughout.
"""

import logging
from datetime import datetime, timezone
from sqlalchemy import text

from app.database import get_session_factory
from app.models.incident import (
    Incident, IncidentType, IncidentSeverity,
    IncidentStatus, IncidentSource,
)
from app.pipeline.women_safety import (
    WOMEN_SAFETY_CATEGORIES, WOMEN_SAFETY_TO_INCIDENT_TYPE,
    get_women_safety_details, is_women_safety_category,
)
from app.services.gemini import gemini_service
from geoalchemy2.elements import WKTElement

logger = logging.getLogger(__name__)

SPAM_THRESHOLD_SECONDS = 30
DUPLICATE_RADIUS_METERS = 100

# Map from pipeline status labels → DB enum values (uppercase as stored)
_STATUS_MAP = {
    "verified":  "APPROVED",   # safety_reports has PENDING/APPROVED/REJECTED
    "duplicate": "REJECTED",   # mark duplicates as rejected
    "spam":      "REJECTED",   # mark spam as rejected
    "pending":   "PENDING",    # keep pending
}


async def process_pending_reports() -> dict:
    logger.info("[COMMUNITY_PIPELINE] process_pending_reports() entered")

    # ── Step 1: Fetch pending safety reports ──────────────────────────────────
    logger.info("[COMMUNITY_PIPELINE] Step 1: Fetching pending safety_reports from DB")
    factory = get_session_factory()
    async with factory() as session:
        result = await session.execute(
            text("""
                SELECT id, user_id, incident_type, severity, latitude, longitude,
                       description, confidence_score, created_at
                FROM safety_reports
                WHERE status = 'PENDING'
                ORDER BY created_at ASC
                LIMIT 50
            """)
        )
        rows = result.fetchall()

    logger.info(f"[COMMUNITY_PIPELINE] Step 1 complete: found {len(rows)} pending report(s)")

    if not rows:
        logger.info("[COMMUNITY_PIPELINE] No pending reports — returning early")
        return {"processed": 0, "message": "No pending reports"}

    reports = []
    for r in rows:
        reports.append({
            "id": str(r[0]),
            "user_id": str(r[1]) if r[1] else None,
            "incident_type": r[2],
            "severity": r[3],
            "latitude": float(r[4]) if r[4] is not None else None,
            "longitude": float(r[5]) if r[5] is not None else None,
            "description": r[6] or "",
            "confidence_score": float(r[7]) if r[7] is not None else 0.0,
            "created_at": r[8],
        })

    # ── Step 2: AI Classification (optional, skipped if Gemini unavailable) ───
    logger.info(f"[COMMUNITY_PIPELINE] Step 2: Classifying {len(reports)} reports via Gemini")
    gemini_available = gemini_service.is_available()
    if not gemini_available:
        logger.warning("[COMMUNITY_PIPELINE] Gemini not available — using passthrough classification")

    classified = []
    for report in reports:
        if not gemini_available:
            report["validated_type"] = report.get("incident_type", "OTHER")
            report["validated_severity"] = report.get("severity", "MEDIUM")
            report["confidence_adjustment"] = 0.0
            report["classification_notes"] = "no_ai"
            report["location_coherent"] = True
            report["description_valid"] = True
            classified.append(report)
            continue

        categories_list = sorted(WOMEN_SAFETY_CATEGORIES.keys())
        prompt = (
            "Validate this community WOMEN'S SAFETY report. Return JSON:\n"
            '{"validated_type": "incident_type", "validated_severity": "LOW|MEDIUM|HIGH|CRITICAL", '
            '"location_coherent": true/false, "description_valid": true/false, '
            '"women_safety_category": "one of [' + ", ".join(categories_list) + '] or null", '
            '"confidence_adjustment": -0.3 to 0.3, "notes": "..."}\n\n'
            "If this is NOT a women's safety incident, set women_safety_category to null.\n\n"
            f"Reported type: {report.get('incident_type', 'unknown')}\n"
            f"Severity: {report.get('severity', 'unknown')}\n"
            f"Location: ({report.get('latitude')}, {report.get('longitude')})\n"
            f"Description: {report.get('description', '')[:500]}"
        )
        try:
            logger.info(f"[COMMUNITY_PIPELINE] LLM call started for report {report['id']}")
            parsed = gemini_service.generate_structured(
                prompt,
                "You are a community report validator. Return ONLY valid JSON.",
            )
            logger.info(f"[COMMUNITY_PIPELINE] LLM response received for report {report['id']}")
            report["validated_type"] = parsed.get("validated_type", report.get("incident_type"))
            report["validated_severity"] = parsed.get("validated_severity", report.get("severity"))
            report["location_coherent"] = parsed.get("location_coherent", True)
            report["description_valid"] = parsed.get("description_valid", True)
            report["confidence_adjustment"] = float(parsed.get("confidence_adjustment", 0.0))
            report["classification_notes"] = parsed.get("notes", "")
        except Exception as e:
            logger.warning(f"[COMMUNITY_PIPELINE] Gemini classification failed for report {report.get('id', '?')}: {e}")
            report["validated_type"] = report.get("incident_type", "OTHER")
            report["validated_severity"] = report.get("severity", "MEDIUM")
            report["confidence_adjustment"] = 0.0
            report["classification_notes"] = "classification_failed"
            report["location_coherent"] = True
            report["description_valid"] = True
        classified.append(report)

    logger.info(f"[COMMUNITY_PIPELINE] Step 2 complete: {len(classified)} reports classified")

    # ── Step 3: Deduplication + Status Resolution + DB Writes ─────────────────
    logger.info("[COMMUNITY_PIPELINE] Step 3: Deduplication, status resolution, and DB writes")
    spam_ids = []
    dup_ids = []
    verified_ids = []
    pending_ids = []

    factory = get_session_factory()
    async with factory() as session:
        for report in classified:
            lat = report.get("latitude")
            lng = report.get("longitude")
            is_dup = False

            # Spatial duplicate check against existing incidents
            if lat is not None and lng is not None:
                try:
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
                        logger.debug(f"[COMMUNITY_PIPELINE] Report {report['id']} is duplicate of incident {dup_row[0]}")
                except Exception as e:
                    logger.warning(f"[COMMUNITY_PIPELINE] Duplicate check failed for report {report['id']}: {e}")

            is_spam = not report.get("description_valid", True) or not report.get("location_coherent", True)
            final_conf = max(0.0, min(1.0,
                report.get("confidence_score", 0.5) + report.get("confidence_adjustment", 0.0)
            ))

            if is_dup:
                pipeline_status = "duplicate"
                dup_ids.append(report["id"])
            elif is_spam:
                pipeline_status = "spam"
                spam_ids.append(report["id"])
            elif final_conf >= 0.4:
                pipeline_status = "verified"
                verified_ids.append(report["id"])
            else:
                pipeline_status = "pending"
                pending_ids.append(report["id"])

            # Map pipeline label → DB enum value (UPPERCASE)
            db_status = _STATUS_MAP.get(pipeline_status, "PENDING")

            # ── FIX: safety_reports does NOT have is_duplicate/duplicate_of ──
            # Those columns only exist on incidents. Remove them from the UPDATE.
            # The DB enum for status is PENDING/APPROVED/REJECTED.
            # "verified" reports → APPROVED; "duplicate"/"spam" → REJECTED.
            logger.info(f"[COMMUNITY_PIPELINE] Updating report {report['id']}: pipeline_status={pipeline_status} db_status={db_status} conf={final_conf:.2f}")
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
                    {
                        "rid": report["id"],
                        "status": db_status,
                        "conf": final_conf,
                    },
                )
                logger.debug(f"[COMMUNITY_PIPELINE] DB write: safety_reports UPDATE OK for {report['id']}")
            except Exception as e:
                logger.error(f"[COMMUNITY_PIPELINE] Failed to update safety_report {report['id']}: {e}")
                await session.rollback()
                continue

            # ── Create an Incident record for verified reports ─────────────────
            if pipeline_status == "verified" and lat is not None and lng is not None:
                try:
                    itype_str = report.get("validated_type") or report.get("incident_type") or "OTHER"
                    sev_str = report.get("validated_severity") or report.get("severity") or "MEDIUM"

                    # Normalize to uppercase for enum lookup (DB stores UPPERCASE)
                    itype_str = itype_str.upper()
                    sev_str = sev_str.upper()

                    try:
                        itype = IncidentType(itype_str)
                    except ValueError:
                        itype = IncidentType.OTHER

                    try:
                        severity = IncidentSeverity(sev_str)
                    except ValueError:
                        severity = IncidentSeverity.MEDIUM

                    # Women-safety category handling
                    ws_cat = report.get("women_safety_category", "")
                    meta = {}
                    if ws_cat and is_women_safety_category(ws_cat):
                        tier, risk_weight, sev_weight, base_sev = get_women_safety_details(ws_cat)
                        meta["women_safety_category"] = ws_cat
                        meta["women_safety_weight"] = sev_weight
                        meta["women_safety_tier"] = tier
                        # Map to correct IncidentType for consistency
                        mapped_type = WOMEN_SAFETY_TO_INCIDENT_TYPE.get(ws_cat)
                        if mapped_type:
                            try:
                                itype = IncidentType(mapped_type)
                            except ValueError:
                                pass
                        if tier == 1:
                            severity = IncidentSeverity.CRITICAL
                        elif tier == 2:
                            severity = IncidentSeverity.HIGH
                    else:
                        # No valid women-safety category — mark as excluded
                        meta["women_safety_category"] = None
                        meta["women_safety_weight"] = None
                        logger.warning(f"[COMMUNITY_PIPELINE] Report {report['id']} has no women_safety_category — excluded from risk/heatmap")

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
                        meta_data=meta,
                    )
                    session.add(incident)
                    logger.info(f"[COMMUNITY_PIPELINE] DB write: incident created from report {report['id']}")
                except Exception as e:
                    logger.error(f"[COMMUNITY_PIPELINE] Failed to create incident from report {report['id']}: {e}")

        logger.info("[COMMUNITY_PIPELINE] Committing all DB changes")
        await session.commit()
        logger.info("[COMMUNITY_PIPELINE] DB commit successful")

    result = {
        "processed": len(reports),
        "verified": len(verified_ids),
        "duplicates": len(dup_ids),
        "spam": len(spam_ids),
        "pending": len(pending_ids),
    }
    logger.info(f"[COMMUNITY_PIPELINE] Complete: {result}")
    return result
