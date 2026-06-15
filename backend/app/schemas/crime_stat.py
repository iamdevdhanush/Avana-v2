from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel


class CrimeStatRecord(BaseModel):
    district: str
    city: Optional[str] = None
    crime_type: str
    crime_category: Optional[str] = None
    crime_count: int
    year: int
    month: Optional[int] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    source_file: Optional[str] = None
    source_name: Optional[str] = None


class CrimeStatResponse(BaseModel):
    id: str
    district: str
    city: Optional[str] = None
    crime_type: str
    crime_category: Optional[str] = None
    crime_count: int
    year: int
    month: Optional[int] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    is_ingested: bool
    created_at: str


class IngestResponse(BaseModel):
    status: str
    batch_id: str
    records_read: int
    records_stored: int
    records_ingested: int
    details: str


class ETLStatusResponse(BaseModel):
    total_records: int
    normalized_records: int
    ingested_records: int
    pending_ingestion: int
    recent_batches: List[str]


class CrimeStatsListResponse(BaseModel):
    records: List[CrimeStatResponse]
    total: int
    page: int
    page_size: int
