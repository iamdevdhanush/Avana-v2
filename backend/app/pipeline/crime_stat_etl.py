"""
ETL pipeline for Karnataka Police crime statistics.

Flow:
  1. Read raw data from CSV/XLSX/PDF files
  2. Normalize (district names, crime categories, dedup, fill coords)
  3. Store normalized records in crime_stats table
  4. Convert crime_stats into Incident records for the existing heatmap engine
  5. Trigger risk score recalculation so heatmap picks up new data
"""
import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import List, Optional, Tuple
from sqlalchemy import select, text, func
from geoalchemy2.elements import WKTElement

from app.database import get_session_factory
from app.models.crime_stat import CrimeStat
from app.models.incident import Incident, IncidentType, IncidentSeverity, IncidentSource, IncidentStatus
from app.models.risk_score import RiskScore
from app.pipeline.crime_stat_normalizer import normalize_records
from app.pipeline.crime_stat_reader import read_csv, read_xlsx, read_pdf
from app.pipeline.karnataka_geo import resolve_coordinates, resolve_district
from app.pipeline.risk import recalculate_all_risk_scores
from app.pipeline.heatmap import generate_heatmap_for_bounds

logger = logging.getLogger(__name__)

CRIME_COUNT_TO_SEVERITY = [
    (0, 10, IncidentSeverity.LOW),
    (11, 50, IncidentSeverity.MEDIUM),
    (51, 100, IncidentSeverity.HIGH),
    (101, float("inf"), IncidentSeverity.CRITICAL),
]

CRIME_COUNT_TO_CONFIDENCE = [
    (0, 10, 20.0),
    (11, 50, 40.0),
    (51, 100, 60.0),
    (101, 500, 80.0),
    (501, float("inf"), 100.0),
]


def crime_count_to_severity(count: int) -> IncidentSeverity:
    for low, high, severity in CRIME_COUNT_TO_SEVERITY:
        if low <= count <= high:
            return severity
    return IncidentSeverity.LOW


def crime_count_to_confidence(count: int) -> float:
    for low, high, conf in CRIME_COUNT_TO_CONFIDENCE:
        if low <= count <= high:
            return conf
    return 10.0


async def read_file(file_path: str, source_name: Optional[str] = None) -> List[dict]:
    if not source_name:
        source_name = file_path.split("/")[-1].split("\\")[-1]
    lower = file_path.lower()
    if lower.endswith(".csv"):
        logger.info(f"Reading CSV: {file_path}")
        with open(file_path, "r", encoding="utf-8-sig") as f:
            content = f.read()
        return read_csv(content, source_name=source_name)
    elif lower.endswith(".xlsx") or lower.endswith(".xls"):
        logger.info(f"Reading XLSX: {file_path}")
        return read_xlsx(file_path, source_name=source_name)
    elif lower.endswith(".pdf"):
        logger.info(f"Reading PDF: {file_path}")
        return read_pdf(file_path, source_name=source_name)
    else:
        logger.error(f"Unsupported file format: {file_path}")
        return []


async def read_text(content: str, format: str = "csv", source_name: str = "text") -> List[dict]:
    if format == "csv":
        return read_csv(content, source_name=source_name)
    else:
        logger.error(f"Unsupported text format: {format}")
        return []


async def load_records_to_db(
    records: List[dict],
    batch_id: str,
) -> Tuple[int, int]:
    if not records:
        return (0, 0)

    factory = get_session_factory()
    async with factory() as session:
        stored = 0
        for r in records:
            exists = await session.execute(
                select(CrimeStat).where(
                    CrimeStat.district == r.get("district"),
                    CrimeStat.crime_category == r.get("crime_category"),
                    CrimeStat.year == r.get("year"),
                    CrimeStat.month == r.get("month") if r.get("month") else CrimeStat.month.is_(None),
                    CrimeStat.crime_type == r.get("crime_type"),
                )
            )
            if exists.scalar_one_or_none():
                continue

            record = CrimeStat(
                district=r.get("district"),
                city=r.get("city"),
                crime_type=r.get("crime_type", ""),
                crime_category=r.get("crime_category"),
                crime_count=r.get("crime_count", 0),
                year=r.get("year", datetime.now().year),
                month=r.get("month"),
                latitude=r.get("latitude"),
                longitude=r.get("longitude"),
                source_file=r.get("source_file"),
                source_name=r.get("source_name"),
                source_row=r.get("source_row"),
                is_normalized=True,
                is_ingested=False,
                ingestion_batch=batch_id,
            )
            session.add(record)
            stored += 1

        await session.commit()
        logger.info(f"Stored {stored} new crime stat records (batch: {batch_id})")
        return (stored, len(records) - stored)


async def ingest_to_incidents(batch_id: Optional[str] = None) -> int:
    factory = get_session_factory()
    async with factory() as session:
        query = select(CrimeStat).where(CrimeStat.is_ingested == False)
        if batch_id:
            query = query.where(CrimeStat.ingestion_batch == batch_id)
        rows = await session.execute(query)
        records = rows.scalars().all()

    if not records:
        logger.info("No uningested crime stats to process")
        return 0

    logger.info(f"Ingesting {len(records)} crime stats as incidents")
    factory = get_session_factory()
    async with factory() as session:
        ingested = 0
        for rec in records:
            lat = rec.latitude
            lng = rec.longitude
            if not lat or not lng:
                resolved_lat, resolved_lng = resolve_coordinates(rec.district, rec.city)
                lat = resolved_lat or 0
                lng = resolved_lng or 0

            severity = crime_count_to_severity(rec.crime_count)
            confidence = crime_count_to_confidence(rec.crime_count)

            dt = datetime(rec.year, rec.month or 1, 1, tzinfo=timezone.utc)
            geom = WKTElement(f"POINT({lng} {lat})", srid=4326)

            # Determine women_safety_category from the crime type
            from app.pipeline.crime_stat_normalizer import resolve_women_safety_category as _resolve_ws
            ws_cat = _resolve_ws(rec.crime_type)
            ws_weight = None
            if ws_cat:
                from app.pipeline.women_safety import get_women_safety_details
                _tier, _risk_wt, ws_weight, _base_sev = get_women_safety_details(ws_cat)

            meta = {
                "crime_stat_id": str(rec.id),
                "crime_count": rec.crime_count,
                "crime_type_raw": rec.crime_type,
                "crime_category": rec.crime_category,
                "women_safety_category": ws_cat,
                "women_safety_weight": ws_weight,
                "source": "karnataka_police_etl",
                "batch_id": rec.ingestion_batch,
                "ingestion_timestamp": datetime.now(timezone.utc).isoformat(),
            }

            incident = Incident(
                incident_type=_to_incident_type(rec.crime_category),
                severity=severity,
                source=IncidentSource.POLICE,
                status=IncidentStatus.VERIFIED,
                confidence_score=confidence,
                latitude=lat,
                longitude=lng,
                geom=geom,
                title=f"{rec.crime_type} in {rec.district} ({rec.year})",
                description=f"Police stat: {rec.crime_count}x {rec.crime_type} in {rec.district}, {rec.year}",
                district=rec.district,
                city=rec.city,
                incident_date=dt,
                source_id=f"crime_stat_{rec.id}",
                source_url=None,
                meta_data=meta,
                ai_classified=False,
                user_id=None,
            )
            session.add(incident)
            rec.is_ingested = True
            ingested += 1

        await session.commit()

    logger.info(f"Ingested {ingested} crime stats as verified incidents")
    return ingested


def _to_incident_type(crime_category: Optional[str]) -> IncidentType:
    if not crime_category:
        return IncidentType.OTHER
    upper = crime_category.strip().upper()
    for t in IncidentType:
        if t.value == upper:
            return t
    return IncidentType.OTHER


async def recalc_heatmap_for_districts():
    factory = get_session_factory()
    async with factory() as session:
        result = await session.execute(
            text("""
                SELECT DISTINCT district FROM crime_stats
                WHERE is_ingested = true
                  AND district IS NOT NULL
            """)
        )
        districts = [r[0] for r in result.fetchall()]

    from app.utils.geo import DISTRICT_BOUNDS
    results = []
    for district in districts:
        resolved = resolve_district(district)
        bounds = DISTRICT_BOUNDS.get(resolved) if resolved else None
        if bounds:
            sw_lat, ne_lat, sw_lng, ne_lng = bounds[0], bounds[1], bounds[2], bounds[3]
            try:
                r = await generate_heatmap_for_bounds(sw_lat - 0.1, sw_lng - 0.1, ne_lat + 0.1, ne_lng + 0.1)
                results.append(r)
                logger.info(f"Heatmap regenerated for {district}")
            except Exception as e:
                logger.error(f"Heatmap regeneration failed for {district}: {e}")
        else:
            logger.warning(f"No bounds for district: {district}")


async def run_etl_pipeline(file_path: Optional[str] = None, content: Optional[str] = None, format: str = "csv") -> dict:
    batch_id = str(uuid.uuid4())[:8]
    logger.info(f"Starting ETL pipeline (batch: {batch_id})")

    records = []
    if file_path:
        records = await read_file(file_path)
    elif content:
        records = await read_text(content, format=format, source_name=f"inline_{format}")
    else:
        return {"status": "error", "message": "No file or content provided"}

    if not records:
        return {"status": "error", "message": "No records extracted from source", "batch_id": batch_id}

    normalized = normalize_records(records)

    stored, skipped = await load_records_to_db(normalized, batch_id)
    if stored == 0:
        return {"status": "ok", "message": "All records already exist (no new data)", "batch_id": batch_id}

    ingested = await ingest_to_incidents(batch_id)

    await recalc_heatmap_for_districts()

    return {
        "status": "success",
        "batch_id": batch_id,
        "records_read": len(records),
        "records_normalized": len(normalized),
        "records_stored": stored,
        "records_skipped": skipped,
        "records_ingested": ingested,
    }


async def get_etl_status() -> dict:
    factory = get_session_factory()
    async with factory() as session:
        total = await session.execute(select(func.count(CrimeStat.id)))
        total_count = total.scalar() or 0

        norm = await session.execute(
            select(func.count(CrimeStat.id)).where(CrimeStat.is_normalized == True)
        )
        norm_count = norm.scalar() or 0

        ingested = await session.execute(
            select(func.count(CrimeStat.id)).where(CrimeStat.is_ingested == True)
        )
        ing_count = ingested.scalar() or 0

        pending = await session.execute(
            select(func.count(CrimeStat.id)).where(CrimeStat.is_ingested == False)
        )
        pend_count = pending.scalar() or 0

        batches = await session.execute(
            select(CrimeStat.ingestion_batch)
            .where(CrimeStat.ingestion_batch.isnot(None))
            .distinct()
            .limit(20)
        )
        batch_list = [r[0] for r in batches.fetchall()]

    return {
        "total_records": total_count,
        "normalized_records": norm_count,
        "ingested_records": ing_count,
        "pending_ingestion": pend_count,
        "recent_batches": batch_list,
    }
