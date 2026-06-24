"""
Intelligence Confidence Model

Produces overall intelligence confidence score (0-100) by combining:
1. AI confidence (from extraction)
2. Source credibility (news, police, community, etc.)
3. Geocoding confidence (district match quality)
4. Duplicate confidence (how unique is this report)
5. Human verification (was it reviewed)

Every incident in the system gets a composite confidence score.
"""

import logging
import math
from typing import Optional

logger = logging.getLogger(__name__)

SOURCE_CREDIBILITY_MAP = {
    "POLICE": 1.0,
    "GOVERNMENT": 0.95,
    "VERIFIED_COMMUNITY": 0.90,
    "COMMUNITY_REPORT": 0.70,
    "NEWS_ENGLISH": 0.65,
    "NEWS_KANNADA": 0.55,
    "USER_REPORT": 0.50,
    "SOS": 0.40,
    "SYSTEM": 0.35,
}

GEOCODING_CONFIDENCE_MAP = {
    "HIGH": 1.0,
    "MEDIUM": 0.7,
    "LOW": 0.4,
}


def get_source_credibility(source: str, source_url: Optional[str] = None) -> float:
    base = SOURCE_CREDIBILITY_MAP.get(source, 0.5)
    if source_url and source.upper() == "NEWS":
        url_lower = source_url.lower()
        if any(kw in url_lower for kw in [".gov.in", ".police.", "data.gov"]):
            return SOURCE_CREDIBILITY_MAP["GOVERNMENT"]
        if any(kw in url_lower for kw in ["kannada", "vijaykarnataka"]):
            return SOURCE_CREDIBILITY_MAP["NEWS_KANNADA"]
    return base


def compute_geocoding_confidence(
    ai_district: Optional[str],
    nominatim_district: Optional[str],
    has_coordinates: bool,
) -> tuple[str, float]:
    if not has_coordinates:
        return ("LOW", 0.0)
    if not ai_district or not nominatim_district:
        return ("MEDIUM", 0.7)
    ai_norm = ai_district.strip().lower().replace(" ", "")
    nom_norm = nominatim_district.strip().lower().replace(" ", "")
    if ai_norm == nom_norm:
        return ("HIGH", 1.0)
    if ai_norm in nom_norm or nom_norm in ai_norm:
        return ("MEDIUM", 0.7)
    return ("LOW", 0.4)


def compute_duplicate_confidence(is_duplicate: bool, duplicate_count: int = 0) -> float:
    if is_duplicate:
        return 0.1
    return min(1.0, 1.0 - (duplicate_count * 0.1))


def compute_human_verification_confidence(
    is_reviewed: bool,
    status: str,
    moderated: bool,
) -> float:
    if not is_reviewed:
        return 0.3
    if status == "VERIFIED":
        return 1.0 if moderated else 0.85
    if status == "DISMISSED":
        return 0.0
    if status == "DUPLICATE":
        return 0.1
    if status == "SPAM":
        return 0.0
    return 0.5


def compute_overall_confidence(
    ai_confidence: float = 0.5,
    source: str = "SYSTEM",
    source_url: Optional[str] = None,
    geocoding_label: str = "MEDIUM",
    geocoding_score: float = 0.7,
    is_duplicate: bool = False,
    duplicate_count: int = 0,
    is_reviewed: bool = False,
    status: str = "PENDING",
    moderated: bool = False,
) -> float:
    """
    Compute overall intelligence confidence (0-100).

    Weight distribution:
    - AI confidence: 25%
    - Source credibility: 25%
    - Geocoding confidence: 20%
    - Duplicate confidence: 10%
    - Human verification: 20%
    """
    source_cred = get_source_credibility(source, source_url)
    dup_conf = compute_duplicate_confidence(is_duplicate, duplicate_count)
    human_conf = compute_human_verification_confidence(is_reviewed, status, moderated)

    overall = (
        ai_confidence * 0.25
        + source_cred * 0.25
        + geocoding_score * 0.20
        + dup_conf * 0.10
        + human_conf * 0.20
    )

    return round(max(0.0, min(1.0, overall)) * 100, 1)


def compute_confidence_for_incident(
    incident_dict: dict,
    geocoding_label: str = "MEDIUM",
    geocoding_score: float = 0.7,
) -> float:
    """
    Convenience wrapper that computes confidence from an incident dict.
    """
    return compute_overall_confidence(
        ai_confidence=float(incident_dict.get("confidence", 0.5)),
        source=str(incident_dict.get("source", "SYSTEM")),
        source_url=incident_dict.get("source_url"),
        geocoding_label=geocoding_label,
        geocoding_score=geocoding_score,
        is_duplicate=bool(incident_dict.get("is_duplicate", False)),
        is_reviewed=str(incident_dict.get("status", "PENDING")) != "PENDING",
        status=str(incident_dict.get("status", "PENDING")),
    )
