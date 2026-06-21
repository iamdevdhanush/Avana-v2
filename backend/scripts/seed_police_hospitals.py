"""
Seed police stations and hospitals from CSV.
Completely offline — no external dependencies.
"""

import csv
import logging
import uuid
import asyncio
import os
from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from app.config import settings
from app.database import Base

logger = logging.getLogger(__name__)

SEED_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "seed_data")


async def seed_police_stations(csv_path: str = None, truncate: bool = False) -> dict:
    if csv_path is None:
        csv_path = os.path.join(SEED_DIR, "police_stations.csv")
    if not os.path.exists(csv_path):
        return {"status": "skipped", "reason": f"CSV not found: {csv_path}"}

    engine = create_async_engine(settings.build_database_url(), echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async_session = async_sessionmaker(engine, expire_on_commit=False)
    inserted = 0

    async with async_session() as db:
        if truncate:
            await db.execute(text("DELETE FROM police_stations"))
            await db.commit()

        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    row_id = row.get("id")
                    station_id = uuid.UUID(row_id) if row_id else uuid.uuid4()
                    lat = float(row["latitude"])
                    lng = float(row["longitude"])

                    await db.execute(
                        text("""
                            INSERT INTO police_stations
                                (id, name, latitude, longitude, geom,
                                 district, city, phone,
                                 has_emergency_number, station_type,
                                 created_at, updated_at)
                            VALUES (
                                :id, :name, :lat, :lng,
                                ST_SetSRID(ST_MakePoint(:lng, :lat), 4326),
                                :district, :city, :phone,
                                :has_emergency, :station_type,
                                NOW(), NOW()
                            )
                            ON CONFLICT (id) DO NOTHING
                        """),
                        {
                            "id": station_id,
                            "name": row["name"],
                            "lat": lat,
                            "lng": lng,
                            "district": row.get("district", ""),
                            "city": row.get("city", ""),
                            "phone": row.get("phone", ""),
                            "has_emergency": row.get("has_emergency_number", "TRUE").upper() == "TRUE",
                            "station_type": row.get("station_type", "police_station"),
                        }
                    )
                    inserted += 1
                except Exception as e:
                    logger.error(f"[SEED] Police station row {reader.line_num}: {e}")

        await db.commit()

    await engine.dispose()
    logger.info(f"[SEED] police_stations: {inserted} inserted")
    return {"status": "ok", "inserted": inserted}


async def seed_hospitals(csv_path: str = None, truncate: bool = False) -> dict:
    if csv_path is None:
        csv_path = os.path.join(SEED_DIR, "hospitals.csv")
    if not os.path.exists(csv_path):
        return {"status": "skipped", "reason": f"CSV not found: {csv_path}"}

    engine = create_async_engine(settings.build_database_url(), echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async_session = async_sessionmaker(engine, expire_on_commit=False)
    inserted = 0

    async with async_session() as db:
        if truncate:
            await db.execute(text("DELETE FROM hospitals"))
            await db.commit()

        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    row_id = row.get("id")
                    hospital_id = uuid.UUID(row_id) if row_id else uuid.uuid4()
                    lat = float(row["latitude"])
                    lng = float(row["longitude"])
                    htype = row.get("hospital_type", "GOVERNMENT").lower()

                    await db.execute(
                        text("""
                            INSERT INTO hospitals
                                (id, name, latitude, longitude, geom,
                                 district, city,
                                 hospital_type, emergency_services,
                                 ambulance_available, trauma_center,
                                 created_at, updated_at)
                            VALUES (
                                :id, :name, :lat, :lng,
                                ST_SetSRID(ST_MakePoint(:lng, :lat), 4326),
                                :district, :city,
                                CAST(:htype AS hospitaltype),
                                :emergency, :ambulance, :trauma,
                                NOW(), NOW()
                            )
                            ON CONFLICT (id) DO NOTHING
                        """),
                        {
                            "id": hospital_id,
                            "name": row["name"],
                            "lat": lat,
                            "lng": lng,
                            "district": row.get("district", ""),
                            "city": row.get("city", ""),
                            "htype": htype,
                            "emergency": row.get("emergency_services", "TRUE").upper() == "TRUE",
                            "ambulance": row.get("ambulance_available", "TRUE").upper() == "TRUE",
                            "trauma": row.get("trauma_center", "FALSE").upper() == "TRUE",
                        }
                    )
                    inserted += 1
                except Exception as e:
                    logger.error(f"[SEED] Hospital row {reader.line_num}: {e}")

        await db.commit()

    await engine.dispose()
    logger.info(f"[SEED] hospitals: {inserted} inserted")
    return {"status": "ok", "inserted": inserted}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(seed_police_stations())
