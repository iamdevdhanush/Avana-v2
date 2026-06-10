from typing import TypedDict, List, Optional
from langgraph.graph import StateGraph, END
import logging
from datetime import datetime, timedelta, timezone
import json
import asyncio
from sqlalchemy import text, select
from geoalchemy2.elements import WKTElement

from app.services.gemini import GeminiService
from app.database import async_session_factory
from app.models.incident import Incident, IncidentType, IncidentSeverity, IncidentStatus

logger = logging.getLogger(__name__)

gemini_service = GeminiService()

SPAM_THRESHOLD_SECONDS = 30
DUPLICATE_RADIUS_METERS = 100
MAX_REPORTS_PER_IP_MINUTE = 5


class CommunityState(TypedDict):
    pending_reports: List[dict]
    classified_reports: List[dict]
    duplicates_found: List[dict]
    spam_detected: List[dict]
    verified_reports: List[dict]
    saved_count: int
    errors: List[str]


def _clean_json_response(text: str) -> str:
    text = text.strip()
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    return text.strip()


async def fetch_pending_reports(state: CommunityState) -> dict:
    async with async_session_factory() as session:
        try:
            result = await session.execute(
                text("""
                    SELECT id, user_id, incident_type, severity, latitude, longitude,
                           description, status, confidence_score, reporter_ip,
                           created_at, source
                    FROM safety_reports
                    WHERE status = 'pending'
                    ORDER BY created_at ASC
                    LIMIT 100
                """)
            )
            rows = result.fetchall()
            reports = []
            for row in rows:
                reports.append({
                    "id": str(row[0]),
                    "user_id": str(row[1]) if row[1] else None,
                    "incident_type": row[2],
                    "severity": row[3],
                    "latitude": float(row[4]) if row[4] else None,
                    "longitude": float(row[5]) if row[5] else None,
                    "description": row[6],
                    "status": row[7],
                    "confidence_score": float(row[8]) if row[8] else 0.0,
                    "reporter_ip": row[9],
                    "created_at": row[10].isoformat() if row[10] else None,
                    "source": row[11],
                })
            logger.info(f"Fetched {len(reports)} pending community reports")
            return {"pending_reports": reports}
        except Exception as e:
            logger.error(f"Failed to fetch pending reports: {e}")
            return {"pending_reports": [], "errors": [str(e)]}


async def classify_report(state: CommunityState) -> dict:
    reports = state.get("pending_reports", [])
    classified = []
    for report in reports:
        prompt = (
            "Validate and classify this community safety report. Return a JSON object:\n"
            "{\n"
            f'  "validated_type": one of [{", ".join(t.value for t in IncidentType)}],\n'
            '  "validated_severity": "low" | "medium" | "high" | "critical",\n'
            '  "location_coherent": true/false,\n'
            '  "description_valid": true/false,\n'
            '  "confidence_adjustment": float -0.3 to 0.3,\n'
            '  "notes": "any issues found"\n'
            "}\n\n"
            f"Reported type: {report.get('incident_type', 'unknown')}\n"
            f"Reported severity: {report.get('severity', 'unknown')}\n"
            f"Location: ({report.get('latitude')}, {report.get('longitude')})\n"
            f"Description: {report.get('description', '')[:500]}\n"
            f"Source: {report.get('source', 'unknown')}"
        )
        try:
            response = gemini_service.generate(
                prompt,
                system_instruction=(
                    "You are a community report validator. Assess if the report is coherent, "
                    "validate the incident type and severity. Return ONLY valid JSON."
                ),
            )
            cleaned = _clean_json_response(response)
            parsed = json.loads(cleaned)
            report["validated_type"] = parsed.get("validated_type", report.get("incident_type"))
            report["validated_severity"] = parsed.get("validated_severity", report.get("severity"))
            report["location_coherent"] = parsed.get("location_coherent", True)
            report["description_valid"] = parsed.get("description_valid", True)
            report["confidence_adjustment"] = float(parsed.get("confidence_adjustment", 0.0))
            report["classification_notes"] = parsed.get("notes", "")
            classified.append(report)
        except Exception as e:
            logger.error(f"Classification failed for report {report.get('id')}: {e}")
            report["validated_type"] = report.get("incident_type", "other")
            report["validated_severity"] = report.get("severity", "medium")
            report["location_coherent"] = True
            report["description_valid"] = True
            report["confidence_adjustment"] = 0.0
            report["classification_notes"] = "classification_failed"
            classified.append(report)
    return {"classified_reports": classified}


async def check_duplicates(state: CommunityState) -> dict:
    reports = state.get("classified_reports", [])
    duplicates = []
    non_duplicates = []
    async with async_session_factory() as session:
        for report in reports:
            lat = report.get("latitude")
            lng = report.get("longitude")
            if lat is None or lng is None:
                non_duplicates.append(report)
                continue
            try:
                result = await session.execute(
                    text("""
                        SELECT id, incident_type, description, latitude, longitude,
                               ST_Distance(
                                   geom::geography,
                                   ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography
                               ) as dist_meters
                        FROM incidents
                        WHERE ST_DWithin(
                            geom::geography,
                            ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography,
                            :radius
                        )
                        ORDER BY dist_meters ASC
                        LIMIT 3
                    """),
                    {"lng": lng, "lat": lat, "radius": DUPLICATE_RADIUS_METERS},
                )
                rows = result.fetchall()
                if rows:
                    match = {
                        "report_id": report["id"],
                        "matched_incidents": [
                            {
                                "id": str(r[0]),
                                "type": r[1],
                                "description": r[2],
                                "distance_meters": float(r[5]),
                            }
                            for r in rows
                        ],
                        "is_duplicate": True,
                    }
                    duplicates.append(match)
                    report["is_duplicate"] = True
                    report["duplicate_of"] = str(rows[0][0])
                else:
                    report["is_duplicate"] = False
                    report["duplicate_of"] = None
                    non_duplicates.append(report)
            except Exception as e:
                logger.error(f"Duplicate check failed for report {report.get('id')}: {e}")
                report["is_duplicate"] = False
                report["duplicate_of"] = None
                non_duplicates.append(report)
    reports[:] = non_duplicates + [r for r in reports if r.get("is_duplicate")]
    return {"duplicates_found": duplicates}


async def detect_spam(state: CommunityState) -> dict:
    reports = state.get("classified_reports", [])
    spam_list = []
    clean_reports = []
    ip_timestamps: dict = {}
    ip_counts: dict = {}
    text_sigs: dict = {}
    for report in reports:
        ip = report.get("reporter_ip", "unknown")
        created_at_str = report.get("created_at")
        created_at = None
        if created_at_str:
            try:
                created_at = datetime.fromisoformat(created_at_str)
            except (ValueError, TypeError):
                created_at = datetime.now(timezone.utc)
        else:
            created_at = datetime.now(timezone.utc)
        if ip not in ip_timestamps:
            ip_timestamps[ip] = []
            ip_counts[ip] = 0
        ip_timestamps[ip].append(created_at)
        ip_counts[ip] += 1
        desc = report.get("description", "").lower().strip()
        if desc:
            words = tuple(sorted(desc.split()[:10]))
            if words not in text_sigs:
                text_sigs[words] = []
            text_sigs[words].append(report)
    for ip, timestamps in ip_timestamps.items():
        if ip_counts[ip] > MAX_REPORTS_PER_IP_MINUTE:
            recent = [t for t in timestamps if (datetime.now(timezone.utc) - t).total_seconds() < 60]
            if len(recent) > MAX_REPORTS_PER_IP_MINUTE:
                logger.warning(f"Spam detected: IP {ip} submitted {len(recent)} reports in 60s")
    for words, group in text_sigs.items():
        if len(group) > 3:
            for rep in group:
                rep["is_spam"] = True
                rep["spam_reason"] = "duplicate_text"
                spam_list.append(rep)
    for report in reports:
        if report.get("is_spam"):
            continue
        if report.get("is_duplicate"):
            if report.get("confidence_adjustment", 0) < 0:
                report["is_spam"] = True
                report["spam_reason"] = "low_confidence_duplicate"
                spam_list.append(report)
                continue
        if not report.get("description_valid", True) or not report.get("location_coherent", True):
            report["is_spam"] = True
            report["spam_reason"] = "invalid_content"
            spam_list.append(report)
            continue
        report["is_spam"] = False
        report["spam_reason"] = None
        clean_reports.append(report)
    return {"spam_detected": spam_list, "classified_reports": clean_reports}


async def generate_confidence(state: CommunityState) -> dict:
    reports = state.get("classified_reports", [])
    verified = []
    for report in reports:
        base = report.get("confidence_score", 0.5)
        adjustment = report.get("confidence_adjustment", 0.0)
        if report.get("is_duplicate"):
            base *= 0.5
        if report.get("is_spam"):
            base = 0.0
        base = max(0.0, min(1.0, base + adjustment))
        report["final_confidence"] = base
        if base >= 0.4 and not report.get("is_spam") and not report.get("is_duplicate"):
            report["final_status"] = IncidentStatus.VERIFIED.value
            verified.append(report)
        elif report.get("is_spam"):
            report["final_status"] = IncidentStatus.SPAM.value
        elif report.get("is_duplicate"):
            report["final_status"] = IncidentStatus.DUPLICATE.value
        else:
            report["final_status"] = IncidentStatus.PENDING.value
            verified.append(report)
    return {"verified_reports": verified}


async def save_results(state: CommunityState) -> dict:
    saved = 0
    errors = list(state.get("errors", []))
    async with async_session_factory() as session:
        for report in state.get("verified_reports", []):
            try:
                await session.execute(
                    text("""
                        UPDATE safety_reports
                        SET status = :status,
                            incident_type = :incident_type,
                            severity = :severity,
                            confidence_score = :confidence,
                            is_duplicate = :is_duplicate,
                            duplicate_of = :duplicate_of,
                            is_spam = :is_spam,
                            spam_reason = :spam_reason,
                            moderated_by = :moderated_by,
                            updated_at = NOW()
                        WHERE id = :id::uuid
                    """),
                    {
                        "id": report["id"],
                        "status": report.get("final_status", "pending"),
                        "incident_type": report.get("validated_type", report.get("incident_type")),
                        "severity": report.get("validated_severity", report.get("severity")),
                        "confidence": report.get("final_confidence", 0.0),
                        "is_duplicate": report.get("is_duplicate", False),
                        "duplicate_of": report.get("duplicate_of"),
                        "is_spam": report.get("is_spam", False),
                        "spam_reason": report.get("spam_reason"),
                        "moderated_by": None,
                    },
                )
                if report.get("final_status") == IncidentStatus.VERIFIED.value:
                    lat = report.get("latitude")
                    lng = report.get("longitude")
                    if lat is not None and lng is not None:
                        try:
                            incident_type_str = report.get("validated_type", report.get("incident_type", "other"))
                            try:
                                incident_type = IncidentType(incident_type_str)
                            except ValueError:
                                incident_type = IncidentType.OTHER
                            severity_str = report.get("validated_severity", report.get("severity", "medium"))
                            try:
                                severity = IncidentSeverity(severity_str)
                            except ValueError:
                                severity = IncidentSeverity.MEDIUM
                            incident = Incident(
                                incident_type=incident_type,
                                severity=severity,
                                source="community_report",
                                status=IncidentStatus.VERIFIED,
                                confidence_score=report.get("final_confidence", 0.5),
                                latitude=lat,
                                longitude=lng,
                                geom=WKTElement(f"POINT({lng} {lat})", srid=4326),
                                description=(report.get("description") or "")[:500],
                                district=report.get("district", ""),
                                city=report.get("city", ""),
                                incident_date=datetime.now(timezone.utc),
                                ai_classified=True,
                            )
                            session.add(incident)
                        except Exception as e:
                            logger.error(f"Failed to create incident from report {report.get('id')}: {e}")
                saved += 1
            except Exception as e:
                logger.error(f"Failed to save report {report.get('id')}: {e}")
                errors.append(str(e))
        await session.commit()
    logger.info(f"Saved {saved} community report results")
    return {"saved_count": saved, "errors": errors}


def build_community_graph() -> StateGraph:
    workflow = StateGraph(CommunityState)
    workflow.add_node("fetch_pending_reports", fetch_pending_reports)
    workflow.add_node("classify_report", classify_report)
    workflow.add_node("check_duplicates", check_duplicates)
    workflow.add_node("detect_spam", detect_spam)
    workflow.add_node("generate_confidence", generate_confidence)
    workflow.add_node("save_results", save_results)
    workflow.set_entry_point("fetch_pending_reports")
    workflow.add_edge("fetch_pending_reports", "classify_report")
    workflow.add_edge("classify_report", "check_duplicates")
    workflow.add_edge("check_duplicates", "detect_spam")
    workflow.add_edge("detect_spam", "generate_confidence")
    workflow.add_edge("generate_confidence", "save_results")
    workflow.add_edge("save_results", END)
    return workflow.compile()


async def run() -> dict:
    initial_state: CommunityState = {
        "pending_reports": [],
        "classified_reports": [],
        "duplicates_found": [],
        "spam_detected": [],
        "verified_reports": [],
        "saved_count": 0,
        "errors": [],
    }
    graph = build_community_graph()
    result = await graph.ainvoke(initial_state)
    logger.info(
        f"Community intelligence completed: "
        f"{result['saved_count']} processed, "
        f"{len(result['duplicates_found'])} duplicates, "
        f"{len(result['spam_detected'])} spam"
    )
    return result


def run_scheduled() -> dict:
    return asyncio.run(run())
