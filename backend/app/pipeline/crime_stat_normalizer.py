"""
Normalization logic for Karnataka Police crime statistics.
Standardizes district names, crime categories, handles duplicates and missing values.
"""
import logging
from typing import Dict, List, Optional, Tuple
from app.pipeline.karnataka_geo import resolve_district, resolve_district_from_city

logger = logging.getLogger(__name__)

CRIME_CATEGORY_MAPPING: Dict[str, str] = {
    "theft": "THEFT",
    "burglary": "BURGLARY",
    "robbery": "ROBBERY",
    "dacoity": "ROBBERY",
    "murder": "MURDER",
    "attempt to murder": "ASSAULT",
    "attempted murder": "ASSAULT",
    "assault": "ASSAULT",
    "grievous hurt": "ASSAULT",
    "hurt": "ASSAULT",
    "kidnapping": "KIDNAPPING",
    "kidnap": "KIDNAPPING",
    "abduction": "KIDNAPPING",
    "rape": "ASSAULT",
    "sexual assault": "ASSAULT",
    "harassment": "HARASSMENT",
    "sexual harassment": "HARASSMENT",
    "stalking": "STALKING",
    "domestic violence": "DOMESTIC_VIOLENCE",
    "dowry death": "DOMESTIC_VIOLENCE",
    "cruelty by husband": "DOMESTIC_VIOLENCE",
    "riots": "RIOT",
    "riot": "RIOT",
    "arson": "VANDALISM",
    "vandalism": "VANDALISM",
    "criminal trespass": "BURGLARY",
    "cheating": "THEFT",
    "fraud": "THEFT",
    "cyber crime": "THEFT",
    "cybercrime": "THEFT",
    "traffic accident": "TRAFFIC_ACCIDENT",
    "road accident": "TRAFFIC_ACCIDENT",
    "accident": "TRAFFIC_ACCIDENT",
    "hit and run": "TRAFFIC_ACCIDENT",
    "motor vehicle theft": "THEFT",
    "vehicle theft": "THEFT",
    "chain snatching": "ROBBERY",
    "snatching": "ROBBERY",
    "pickpocketing": "PICKPOCKETING",
    "extortion": "ROBBERY",
    "kidnapping for ransom": "KIDNAPPING",
    "possession of arms": "OTHER",
    "unlawful assembly": "RIOT",
    "criminal intimidation": "HARASSMENT",
    "forgery": "THEFT",
    "counterfeiting": "THEFT",
    "drug trafficking": "OTHER",
    "ndps act": "OTHER",
    "narcotic": "OTHER",
    "gambling": "OTHER",
    "immoral traffic": "OTHER",
    "sarson": "OTHER",
    "forest offence": "OTHER",
    "electricity theft": "THEFT",
    "cattle theft": "THEFT",
    "dacoity preparation": "ROBBERY",
    "rioting": "RIOT",
    "murder with robbery": "MURDER",
}

UNKNOWN_CATEGORY = "OTHER"


def normalize_district(district: Optional[str], city: Optional[str] = None) -> Tuple[Optional[str], Optional[str]]:
    if not district and not city:
        return (None, None)

    resolved = None
    if district:
        resolved = resolve_district(district)
    if not resolved and city:
        resolved = resolve_district_from_city(city)
    if not resolved and district:
        normalized = district.strip().title()
        resolved = normalized

    if not resolved and city:
        normalized = city.strip().title()
        resolved = normalized

    return (resolved, city.strip().title() if city else None)


def normalize_crime_category(crime_type: str) -> str:
    if not crime_type:
        return UNKNOWN_CATEGORY
    normalized = crime_type.lower().strip()
    if normalized in CRIME_CATEGORY_MAPPING:
        return CRIME_CATEGORY_MAPPING[normalized]
    for pattern, category in CRIME_CATEGORY_MAPPING.items():
        if pattern in normalized:
            return category
    logger.debug(f"Unmapped crime type: '{crime_type}' -> {UNKNOWN_CATEGORY}")
    return UNKNOWN_CATEGORY


def deduplicate_records(records: List[dict]) -> List[dict]:
    seen = set()
    deduped = []
    for r in records:
        key = (
            str(r.get("district", "")).lower().strip(),
            str(r.get("crime_type", "")).lower().strip(),
            str(r.get("crime_category", "")),
            r.get("year"),
            r.get("month"),
        )
        if key not in seen:
            seen.add(key)
            deduped.append(r)
        else:
            logger.debug(f"Removed duplicate: {key}")
    logger.info(f"Deduplication: {len(records)} → {len(deduped)} records")
    return deduped


def fill_missing_coordinates(records: List[dict]) -> List[dict]:
    from app.pipeline.karnataka_geo import resolve_coordinates

    filled = 0
    for r in records:
        if not r.get("latitude") or not r.get("longitude"):
            lat, lng = resolve_coordinates(
                district=r.get("district"),
                city=r.get("city"),
            )
            if lat and lng:
                r["latitude"] = lat
                r["longitude"] = lng
                filled += 1
    if filled:
        logger.info(f"Resolved coordinates for {filled} records using district/city centroids")
    return records


def normalize_records(records: List[dict]) -> List[dict]:
    normalized = []
    for r in records:
        district, city = normalize_district(
            r.get("district"),
            r.get("city"),
        )
        crime_category = normalize_crime_category(r.get("crime_type", ""))
        record = {
            "district": district,
            "city": city,
            "crime_type": r.get("crime_type", ""),
            "crime_category": crime_category,
            "crime_count": int(r.get("crime_count", 0)),
            "year": int(r.get("year", 0)),
            "month": int(r["month"]) if r.get("month") else None,
            "latitude": r.get("latitude"),
            "longitude": r.get("longitude"),
            "source_file": r.get("source_file"),
            "source_name": r.get("source_name"),
            "source_row": r.get("source_row"),
        }
        normalized.append(record)

    normalized = deduplicate_records(normalized)
    normalized = fill_missing_coordinates(normalized)
    normalized = _aggregate_duplicates(normalized)

    return normalized


def _aggregate_duplicates(records: List[dict]) -> List[dict]:
    merged = {}
    for r in records:
        key = (
            r["district"],
            r["crime_category"],
            r["year"],
            r["month"],
        )
        if key in merged:
            merged[key]["crime_count"] += r["crime_count"]
        else:
            merged[key] = dict(r)
    result = list(merged.values())
    if len(result) != len(records):
        logger.info(f"Post-dedup aggregation: {len(records)} → {len(result)} records")
    return result
