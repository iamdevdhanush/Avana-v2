"""
Seed incidents from CSV into the incidents table.
Completely offline — no AI, no Gemini, no scraping.
"""

import csv
import logging
import uuid
import asyncio
import os
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from geoalchemy2.elements import WKTElement

from app.config import settings
from app.database import Base

logger = logging.getLogger(__name__)

SEED_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "seed_data")

WOMEN_SAFETY_WEIGHTS = {
    "Rape": (99.0, 1),
    "Acid Attack": (99.0, 1),
    "Molestation": (75.0, 2),
    "Stalking": (70.0, 2),
    "Domestic Violence": (70.0, 2),
    "Sexual Harassment": (75.0, 2),
    "Assault": (75.0, 2),
    "Harassment": (55.0, 3),
}

SEVERITY_ORDER = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}
SEVERITY_FROM_WS = {
    1: "CRITICAL",
    2: "HIGH",
    3: "MEDIUM",
}


def parse_severity(val: Optional[str], ws_cat: Optional[str]) -> str:
    if val and val.strip().upper() in SEVERITY_ORDER:
        return val.strip().upper()
    if ws_cat:
        _, tier = WOMEN_SAFETY_WEIGHTS.get(ws_cat, (70.0, 2))
        return SEVERITY_FROM_WS.get(tier, "MEDIUM")
    return "MEDIUM"


def parse_incident_type(val: Optional[str], ws_cat: Optional[str]) -> str:
    type_map = {
        "THEFT": "THEFT", "ASSAULT": "ASSAULT", "HARASSMENT": "HARASSMENT",
        "ROBBERY": "ROBBERY", "STALKING": "STALKING",
        "DOMESTIC_VIOLENCE": "DOMESTIC_VIOLENCE", "TRAFFIC_ACCIDENT": "TRAFFIC_ACCIDENT",
        "PICKPOCKETING": "PICKPOCKETING", "BURGLARY": "BURGLARY",
        "MURDER": "MURDER", "KIDNAPPING": "KIDNAPPING", "RIOT": "RIOT",
        "VANDALISM": "VANDALISM", "SUSPICIOUS_ACTIVITY": "SUSPICIOUS_ACTIVITY",
        "OTHER": "OTHER", "sexual_assault": "ASSAULT", "domestic_violence": "DOMESTIC_VIOLENCE",
        "assault": "ASSAULT", "harassment": "HARASSMENT",
    }
    ws_to_type = {
        "Rape": "ASSAULT", "Acid Attack": "ASSAULT", "Molestation": "HARASSMENT",
        "Stalking": "STALKING", "Domestic Violence": "DOMESTIC_VIOLENCE",
        "Sexual Harassment": "HARASSMENT", "Assault": "ASSAULT", "Harassment": "HARASSMENT",
    }
    if val:
        normalized = val.strip().upper().replace(" ", "_")
        direct = type_map.get(val.strip())
        if direct:
            return direct
        if normalized in type_map:
            return type_map[normalized]
    if ws_cat and ws_cat in ws_to_type:
        return ws_to_type[ws_cat]
    return "OTHER"


async def seed_incidents(csv_path: Optional[str] = None, truncate: bool = False) -> dict:
    if csv_path is None:
        csv_path = os.path.join(SEED_DIR, "incidents.csv")

    if not os.path.exists(csv_path):
        return {"status": "skipped", "reason": f"CSV not found: {csv_path}"}

    engine = create_async_engine(settings.build_database_url(), echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async_session = async_sessionmaker(engine, expire_on_commit=False)
    inserted = 0
    skipped = 0
    errors = 0

    async with async_session() as db:
        if truncate:
            await db.execute(text("DELETE FROM incidents WHERE source = 'NEWS'"))
            await db.commit()
            logger.info("[SEED] Truncated existing NEWS incidents")

        existing_count = await db.execute(text("SELECT COUNT(*) FROM incidents"))
        if existing_count.scalar() or 0 > 0 and not truncate:
            logger.info(f"[SEED] incidents table has {existing_count.scalar()} rows — skipping seed")
            return {"status": "skipped", "reason": "incidents already seeded"}

        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    ws_cat = row.get("women_safety_category", "").strip()
                    ws_weight, ws_tier = WOMEN_SAFETY_WEIGHTS.get(ws_cat, (None, None))

                    lat = float(row["latitude"])
                    lng = float(row["longitude"])
                    incident_type = parse_incident_type(row.get("incident_type", ""), ws_cat)
                    severity = parse_severity(row.get("severity", ""), ws_cat)

                    meta = {}
                    if ws_cat and ws_weight:
                        meta["women_safety_category"] = ws_cat
                        meta["women_safety_weight"] = ws_weight
                        meta["women_safety_tier"] = ws_tier
                    else:
                        meta["women_safety_category"] = None
                        meta["women_safety_weight"] = None

                    incident_id = row.get("id")
                    if incident_id:
                        incident_id = uuid.UUID(incident_id)
                    else:
                        incident_id = uuid.uuid4()

                    await db.execute(
                        text("""
                            INSERT INTO incidents
                                (id, incident_type, severity, source, status,
                                 latitude, longitude, geom,
                                 title, description, address,
                                 district, city,
                                 incident_date, created_at, updated_at,
                                 confidence_score, ai_classified,
                                 metadata)
                            VALUES (
                                :id,
                                CAST(:incident_type AS incidenttype),
                                CAST(:severity AS incidentseverity),
                                CAST(:source AS incidentsource),
                                CAST(:status AS incidentstatus),
                                :lat, :lng,
                                ST_SetSRID(ST_MakePoint(:lng, :lat), 4326),
                                :title, :desc, :addr,
                                :district, :city,
                                :incident_date, NOW(), NOW(),
                                :confidence, :ai_classified,
                                :meta::jsonb
                            )
                            ON CONFLICT (id) DO UPDATE SET
                                title = EXCLUDED.title,
                                severity = EXCLUDED.severity,
                                updated_at = NOW()
                        """),
                        {
                            "id": incident_id,
                            "incident_type": incident_type,
                            "severity": severity,
                            "source": row.get("source", "NEWS"),
                            "status": row.get("status", "VERIFIED"),
                            "lat": lat,
                            "lng": lng,
                            "title": row.get("title", "")[:500],
                            "desc": row.get("description", "")[:500],
                            "addr": row.get("address", "")[:500],
                            "district": row.get("district", ""),
                            "city": row.get("city", ""),
                            "incident_date": row.get("incident_date", datetime.now(timezone.utc).strftime("%Y-%m-%d")),
                            "confidence": float(row.get("confidence_score", 0.8)),
                            "ai_classified": False,
                            "meta": str(meta),
                        }
                    )
                    inserted += 1
                except Exception as e:
                    logger.error(f"[SEED] Failed to insert row {reader.line_num}: {e}")
                    errors += 1
                    if errors > 10:
                        logger.error("[SEED] Too many errors — aborting")
                        break

        await db.commit()

    await engine.dispose()

    logger.info(f"[SEED] incidents: {inserted} inserted, {skipped} skipped, {errors} errors")
    return {"status": "ok", "inserted": inserted, "skipped": skipped, "errors": errors}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(seed_incidents())
