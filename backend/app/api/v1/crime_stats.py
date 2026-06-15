"""
API endpoints for Karnataka Police crime statistics ETL.
Integrates with the existing heatmap infrastructure — no new heatmap engine.
"""
import logging
import os
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query, status
from sqlalchemy import select, func, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import require_admin
from app.models.user import User
from app.models.crime_stat import CrimeStat
from app.schemas.crime_stat import (
    CrimeStatRecord,
    CrimeStatResponse,
    CrimeStatsListResponse,
    IngestResponse,
    ETLStatusResponse,
)
from app.pipeline.crime_stat_etl import (
    run_etl_pipeline,
    read_file,
    ingest_to_incidents,
    recalc_heatmap_for_districts,
    get_etl_status,
)
from app.pipeline.crime_stat_normalizer import normalize_records
from app.pipeline.crime_stat_reader import read_csv, read_xlsx

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/crime-stats", tags=["Crime Statistics ETL"])


@router.post("/upload", response_model=IngestResponse)
async def upload_crime_stats(
    file: UploadFile = File(...),
    admin: User = Depends(require_admin),
):
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")

    temp_dir = "data/uploads"
    os.makedirs(temp_dir, exist_ok=True)
    temp_path = os.path.join(temp_dir, file.filename)

    try:
        content = await file.read()
        with open(temp_path, "wb") as f:
            f.write(content)

        result = await run_etl_pipeline(file_path=temp_path)
    except Exception as e:
        logger.error(f"ETL pipeline failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"ETL pipeline failed: {str(e)}")
    finally:
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                pass

    if result.get("status") == "error":
        raise HTTPException(status_code=400, detail=result.get("message"))

    return IngestResponse(
        status=result.get("status", "ok"),
        batch_id=result.get("batch_id", ""),
        records_read=result.get("records_read", 0),
        records_stored=result.get("records_stored", 0),
        records_ingested=result.get("records_ingested", 0),
        details=f"Read {result.get('records_read', 0)} records, stored {result.get('records_stored', 0)}, ingested {result.get('records_ingested', 0)}",
    )


@router.post("/ingest/text", response_model=IngestResponse)
async def ingest_crime_stats_text(
    data: CrimeStatRecord,
    admin: User = Depends(require_admin),
):
    from app.pipeline.crime_stat_normalizer import normalize_records
    from app.pipeline.crime_stat_etl import load_records_to_db, ingest_to_incidents, recalc_heatmap_for_districts
    import uuid

    batch_id = str(uuid.uuid4())[:8]

    raw = [{
        "district": data.district,
        "city": data.city,
        "crime_type": data.crime_type,
        "crime_count": data.crime_count,
        "year": data.year,
        "month": data.month,
        "latitude": data.latitude,
        "longitude": data.longitude,
        "source_name": data.source_name or "api",
    }]
    normalized = normalize_records(raw)
    stored, _ = await load_records_to_db(normalized, batch_id)
    ingested = await ingest_to_incidents(batch_id)
    await recalc_heatmap_for_districts()

    return IngestResponse(
        status="success",
        batch_id=batch_id,
        records_read=1,
        records_stored=stored,
        records_ingested=ingested,
        details=f"Stored {stored}, ingested {ingested}",
    )


@router.post("/ingest-all", response_model=IngestResponse)
async def ingest_all_pending(admin: User = Depends(require_admin)):
    ingested = await ingest_to_incidents()
    if ingested:
        await recalc_heatmap_for_districts()

    return IngestResponse(
        status="success",
        batch_id="bulk",
        records_read=0,
        records_stored=0,
        records_ingested=ingested,
        details=f"Ingested {ingested} pending crime stats as incidents",
    )


@router.get("/status", response_model=ETLStatusResponse)
async def get_crime_stat_status(admin: User = Depends(require_admin)):
    return await get_etl_status()


@router.get("/records", response_model=CrimeStatsListResponse)
async def list_crime_stats(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    district: Optional[str] = None,
    year: Optional[int] = None,
    ingested: Optional[bool] = None,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    query = select(CrimeStat)
    if district:
        query = query.where(CrimeStat.district == district)
    if year:
        query = query.where(CrimeStat.year == year)
    if ingested is not None:
        query = query.where(CrimeStat.is_ingested == ingested)

    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    offset = (page - 1) * page_size
    query = query.order_by(CrimeStat.created_at.desc()).offset(offset).limit(page_size)
    rows = await db.execute(query)
    records = rows.scalars().all()

    return CrimeStatsListResponse(
        records=[
            CrimeStatResponse(
                id=str(r.id),
                district=r.district,
                city=r.city,
                crime_type=r.crime_type,
                crime_category=r.crime_category,
                crime_count=r.crime_count,
                year=r.year,
                month=r.month,
                latitude=r.latitude,
                longitude=r.longitude,
                is_ingested=r.is_ingested,
                created_at=r.created_at.isoformat() if r.created_at else "",
            )
            for r in records
        ],
        total=total,
        page=page,
        page_size=page_size,
    )
