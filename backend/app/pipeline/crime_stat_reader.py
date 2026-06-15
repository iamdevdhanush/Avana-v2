"""
File readers for Karnataka Police datasets.
Supports CSV, XLSX, and PDF tabular extraction.
"""
import csv
import io
import logging
import re
from typing import List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


def detect_separator(sample: str) -> str:
    lines = sample.strip().splitlines()
    if not lines:
        return ","
    header = lines[0]
    for sep in ["\t", "|", ";", ","]:
        if sep in header:
            return sep
    return ","


def read_csv(content: str, source_name: str = "csv") -> List[dict]:
    records = []
    sep = detect_separator(content[:4096])
    reader = csv.DictReader(io.StringIO(content), delimiter=sep)
    if not reader.fieldnames:
        logger.warning(f"No headers found in CSV: {source_name}")
        return records
    for i, row in enumerate(reader):
        cleaned = {k.strip().lower(): v.strip() if v else "" for k, v in row.items()}
        record = _map_columns(cleaned, source_name, row_index=i + 1)
        if record:
            records.append(record)
    logger.info(f"Read {len(records)} records from CSV: {source_name}")
    return records


def read_xlsx(file_path: str, source_name: str = "xlsx") -> List[dict]:
    records = []
    try:
        import openpyxl
    except ImportError:
        logger.error("openpyxl not installed. Install with: pip install openpyxl")
        return records

    try:
        wb = openpyxl.load_workbook(file_path, read_only=True, data_only=True)
        ws = wb.active
        if not ws:
            logger.warning(f"No active sheet in XLSX: {file_path}")
            return records

        rows = list(ws.iter_rows(values_only=True))
        if not rows:
            return records

        headers = [str(h).strip().lower() if h else f"col_{i}" for i, h in enumerate(rows[0])]
        for i, row in enumerate(rows[1:], start=1):
            if all(v is None or str(v).strip() == "" for v in row):
                continue
            row_dict = {}
            for j, h in enumerate(headers):
                val = row[j] if j < len(row) else None
                row_dict[h] = str(val).strip() if val is not None else ""
            record = _map_columns(row_dict, source_name, row_index=i)
            if record:
                records.append(record)
        wb.close()
    except Exception as e:
        logger.error(f"Failed to read XLSX {file_path}: {e}")

    logger.info(f"Read {len(records)} records from XLSX: {file_path}")
    return records


def read_pdf(file_path: str, source_name: str = "pdf") -> List[dict]:
    records = []
    try:
        import pdfplumber
    except ImportError:
        logger.error("pdfplumber not installed. Install with: pip install pdfplumber")
        return records

    try:
        with pdfplumber.open(file_path) as pdf:
            for page_num, page in enumerate(pdf.pages, start=1):
                tables = page.extract_tables()
                for table in tables:
                    if not table or len(table) < 2:
                        continue
                    headers = [str(h).strip().lower() if h else f"col_{i}" for i, h in enumerate(table[0])]
                    for i, row in enumerate(table[1:], start=1):
                        if all(cell is None or str(cell).strip() == "" for cell in row):
                            continue
                        row_dict = {}
                        for j, h in enumerate(headers):
                            val = row[j] if j < len(row) else None
                            row_dict[h] = str(val).strip() if val is not None else ""
                        record = _map_columns(row_dict, f"{source_name}_p{page_num}", row_index=i)
                        if record:
                            records.append(record)
    except Exception as e:
        logger.error(f"Failed to read PDF {file_path}: {e}")

    logger.info(f"Read {len(records)} records from PDF: {file_path}")
    return records


HEADER_ALIASES = {
    "district": ["district", "district_name", "dist", "district name", "region", "division"],
    "city": ["city", "town", "urban", "location", "place", "area", "locality", "police station", "ps"],
    "crime_type": [
        "crime_type", "crime type", "crime", "offence", "offense", "crime head",
        "type of crime", "offence_head", "offence head", "nature of crime",
        "nature_of_offence", "nature of offence", "category", "incident type",
    ],
    "crime_count": [
        "crime_count", "crime count", "count", "incidents", "cases", "reported",
        "number_of_cases", "number of cases", "total", "cases reported",
        "incidents reported", "value", "frequency", "total cases", "no_of_cases",
        "no of cases", "fir", "firs", "firs registered", "cognizable",
        "IPC", "SLL", "total_crime", "crime_total",
    ],
    "year": ["year", "yr", "fiscal_year", "fiscal year", "financial_year", "financial year", "reporting_year", "reporting year"],
    "month": ["month", "mon", "reporting_month", "reporting month", "period"],
}


def _map_columns(row: dict, source_name: str, row_index: int) -> Optional[dict]:
    def _find_col(aliases: List[str]) -> Optional[str]:
        for alias in aliases:
            if alias in row:
                return alias
        return None

    district_col = _find_col(HEADER_ALIASES["district"])
    city_col = _find_col(HEADER_ALIASES["city"])
    type_col = _find_col(HEADER_ALIASES["crime_type"])
    count_col = _find_col(HEADER_ALIASES["crime_count"])
    year_col = _find_col(HEADER_ALIASES["year"])
    month_col = _find_col(HEADER_ALIASES["month"])

    district = row.get(district_col, "") if district_col else ""
    city = row.get(city_col, "") if city_col else ""
    crime_type = row.get(type_col, "") if type_col else ""
    raw_count = row.get(count_col, "0") if count_col else "0"
    raw_year = row.get(year_col, "") if year_col else ""
    raw_month = row.get(month_col, "") if month_col else ""

    if not crime_type and not district:
        return None

    crime_count = _parse_int(raw_count)
    year = _parse_int(raw_year)
    month = _parse_month(raw_month)

    if year == 0:
        year = datetime.now().year
    if crime_count == 0 and raw_count.strip() not in ("0", ""):
        crime_count = 0

    lat_col = None
    lng_col = None
    for col in row:
        cl = col.strip().lower()
        if cl in ("latitude", "lat", "latitud"):
            lat_col = col
        if cl in ("longitude", "lng", "long", "lon", "longitud"):
            lng_col = col

    latitude = _parse_float(row.get(lat_col)) if lat_col else None
    longitude = _parse_float(row.get(lng_col)) if lng_col else None

    return {
        "district": district,
        "city": city,
        "crime_type": crime_type,
        "crime_count": crime_count,
        "year": year,
        "month": month,
        "latitude": latitude,
        "longitude": longitude,
        "source_file": source_name,
        "source_name": source_name,
        "source_row": f"row_{row_index}",
    }


def _parse_int(val) -> int:
    if isinstance(val, (int, float)):
        return int(val)
    if not val:
        return 0
    cleaned = re.sub(r"[^\d]", "", str(val).strip())
    try:
        return int(cleaned) if cleaned else 0
    except (ValueError, TypeError):
        return 0


def _parse_float(val) -> Optional[float]:
    if isinstance(val, (int, float)):
        return float(val)
    if not val:
        return None
    cleaned = str(val).strip().replace(",", "")
    try:
        return float(cleaned)
    except (ValueError, TypeError):
        return None


MONTH_MAP = {
    "january": 1, "jan": 1, "01": 1, "1": 1,
    "february": 2, "feb": 2, "02": 2, "2": 2,
    "march": 3, "mar": 3, "03": 3, "3": 3,
    "april": 4, "apr": 4, "04": 4, "4": 4,
    "may": 5, "05": 5, "5": 5,
    "june": 6, "jun": 6, "06": 6, "6": 6,
    "july": 7, "jul": 7, "07": 7, "7": 7,
    "august": 8, "aug": 8, "08": 8, "8": 8,
    "september": 9, "sep": 9, "09": 9, "9": 9,
    "october": 10, "oct": 10, "10": 10,
    "november": 11, "nov": 11, "11": 11,
    "december": 12, "dec": 12, "12": 12,
}

YEAR_MONTH_PATTERN = re.compile(r"(\d{4})\s*[-_/]\s*(\d{1,2})")
MONTH_YEAR_PATTERN = re.compile(r"(\d{1,2})\s*[-_/]\s*(\d{4})")


def _parse_month(val) -> Optional[int]:
    if not val:
        return None
    cleaned = str(val).strip().lower()
    if cleaned in MONTH_MAP:
        return MONTH_MAP[cleaned]
    m = YEAR_MONTH_PATTERN.match(cleaned)
    if m:
        return int(m.group(2))
    m = MONTH_YEAR_PATTERN.match(cleaned)
    if m:
        return int(m.group(1))
    return None
