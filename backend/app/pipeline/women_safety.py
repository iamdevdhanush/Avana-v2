"""
Women's Safety Taxonomy for AVANA.

Central definition of:
- Crime categories relevant to women's safety (Tiers 1-3)
- Severity mapping per category
- Risk weights (Tier 1=100, Tier 2=70, Tier 3=40)
- Recency multipliers for risk scoring
- Category → IncidentType mapping

Every pipeline (intelligence, ETL, community, risk, heatmap) MUST
reference this file as the single source of truth.
"""

from typing import Dict, Tuple, Optional

# ── Women Safety Categories ──
# (tier, risk_weight, severity_weight, base_severity)
# tier: 1=Critical, 2=High, 3=Moderate
# risk_weight: used for risk score calculation
# severity_weight: used for severity penalty calculation
# base_severity: default IncidentSeverity string

WOMEN_SAFETY_CATEGORIES: Dict[str, Tuple[int, int, int, str]] = {
    # Tier 1 – Critical (weight 100)
    "Rape":                       (1, 100, 100, "CRITICAL"),
    "Gang Rape":                  (1, 100, 100, "CRITICAL"),
    "Attempt to Rape":            (1, 100,  90, "CRITICAL"),
    "Sexual Assault":             (1, 100,  90, "CRITICAL"),
    "Sexual Harassment":          (1,  80,  75, "HIGH"),
    "Molestation":                (1,  85,  80, "HIGH"),
    "Stalking":                   (1,  75,  70, "HIGH"),
    "Cyber Stalking":             (1,  70,  65, "HIGH"),
    "Voyeurism":                  (1,  75,  70, "HIGH"),
    "Kidnapping of Women":        (1,  95,  90, "CRITICAL"),
    "Abduction of Women":         (1,  95,  90, "CRITICAL"),
    "Human Trafficking":          (1, 100, 100, "CRITICAL"),
    "Forced Prostitution":        (1, 100, 100, "CRITICAL"),
    "Acid Attack":                (1, 100, 100, "CRITICAL"),
    "POCSO Sexual Assault":       (1, 100,  95, "CRITICAL"),
    "POCSO Rape":                 (1, 100, 100, "CRITICAL"),

    # Tier 2 – High (weight 70)
    "Domestic Violence":          (2,  70,  65, "HIGH"),
    "Cruelty by Husband":         (2,  70,  65, "HIGH"),
    "Dowry Harassment":           (2,  70,  65, "HIGH"),
    "Dowry Death":                (2,  70,  70, "CRITICAL"),
    "Assault Against Women":      (2,  65,  60, "HIGH"),
    "Murder of Women":            (2,  80,  80, "CRITICAL"),
    "Attempted Murder of Women":  (2,  75,  75, "CRITICAL"),
    "Online Harassment":          (2,  60,  55, "MEDIUM"),
    "Cyber Harassment":           (2,  60,  55, "MEDIUM"),
    "Blackmail":                  (2,  55,  50, "MEDIUM"),
    "Threats Against Women":      (2,  55,  50, "MEDIUM"),

    # Tier 3 – Moderate (weight 40)
    "Chain Snatching":            (3,  40,  35, "MEDIUM"),
    "Robbery Against Women":      (3,  40,  35, "MEDIUM"),
    "Drug Activity":              (3,  35,  30, "MEDIUM"),
    "Gang Activity":              (3,  35,  30, "MEDIUM"),
    "Public Harassment":          (3,  40,  35, "MEDIUM"),
    "Unsafe Transport":           (3,  40,  35, "MEDIUM"),
    "Harassment Near Schools":    (3,  45,  40, "MEDIUM"),
    "Harassment Near Colleges":   (3,  45,  40, "MEDIUM"),
    "Harassment Near Hostels":    (3,  45,  40, "MEDIUM"),
    "Harassment Near Workplaces": (3,  45,  40, "MEDIUM"),
}

# ── Recency multipliers ──
# Applied to incident weight based on incident_date age (in days)
RECENCY_MULTIPLIERS = [
    (30,  1.0),    # 0-30 days: full weight
    (90,  0.8),    # 31-90 days: 80%
    (180, 0.6),    # 91-180 days: 60%
    (365, 0.4),    # 181-365 days: 40%
    (None, 0.2),   # >365 days: 20%
]

# ── Legacy incident_type → women_safety_category mapping ──
# For backfilling existing incidents based on their incident_type
INCIDENT_TYPE_TO_WOMEN_SAFETY: Dict[str, str] = {
    "HARASSMENT": "Sexual Harassment",
    "STALKING": "Stalking",
    "DOMESTIC_VIOLENCE": "Domestic Violence",
    "ASSAULT": "Assault Against Women",
    "MURDER": "Murder of Women",
    "KIDNAPPING": "Kidnapping of Women",
    "ROBBERY": "Robbery Against Women",
    "SEXUAL_ASSAULT": "Sexual Assault",
    "RAPE": "Rape",
    "GANG_RAPE": "Gang Rape",
    "HUMAN_TRAFFICKING": "Human Trafficking",
    "ACID_ATTACK": "Acid Attack",
    "POCSO_RAPE": "POCSO Rape",
    "POCSO_SEXUAL_ASSAULT": "POCSO Sexual Assault",
    "DOWRY_DEATH": "Dowry Death",
    "DOWRY_HARASSMENT": "Dowry Harassment",
    "CRUELTY_BY_HUSBAND": "Cruelty by Husband",
    "CYBER_HARASSMENT": "Cyber Harassment",
    "ONLINE_HARASSMENT": "Online Harassment",
    "BLACKMAIL": "Blackmail",
    "THREATS": "Threats Against Women",
    "CHAIN_SNATCHING": "Chain Snatching",
    "PUBLIC_HARASSMENT": "Public Harassment",
    "UNSAFE_TRANSPORT": "Unsafe Transport",
}

# ── Category to IncidentType mapping ──
# Women-safety categories get mapped to broader IncidentType for backward compat
WOMEN_SAFETY_TO_INCIDENT_TYPE: Dict[str, str] = {
    "Rape": "SEXUAL_ASSAULT",
    "Gang Rape": "SEXUAL_ASSAULT",
    "Attempt to Rape": "ASSAULT",
    "Sexual Assault": "SEXUAL_ASSAULT",
    "Sexual Harassment": "HARASSMENT",
    "Molestation": "HARASSMENT",
    "Stalking": "STALKING",
    "Cyber Stalking": "STALKING",
    "Voyeurism": "HARASSMENT",
    "Kidnapping of Women": "KIDNAPPING",
    "Abduction of Women": "KIDNAPPING",
    "Human Trafficking": "KIDNAPPING",
    "Forced Prostitution": "KIDNAPPING",
    "Acid Attack": "ASSAULT",
    "POCSO Sexual Assault": "SEXUAL_ASSAULT",
    "POCSO Rape": "SEXUAL_ASSAULT",
    "Domestic Violence": "DOMESTIC_VIOLENCE",
    "Cruelty by Husband": "DOMESTIC_VIOLENCE",
    "Dowry Harassment": "HARASSMENT",
    "Dowry Death": "MURDER",
    "Assault Against Women": "ASSAULT",
    "Murder of Women": "MURDER",
    "Attempted Murder of Women": "ASSAULT",
    "Online Harassment": "HARASSMENT",
    "Cyber Harassment": "HARASSMENT",
    "Blackmail": "HARASSMENT",
    "Threats Against Women": "HARASSMENT",
    "Chain Snatching": "ROBBERY",
    "Robbery Against Women": "ROBBERY",
    "Drug Activity": "SUSPICIOUS_ACTIVITY",
    "Gang Activity": "SUSPICIOUS_ACTIVITY",
    "Public Harassment": "HARASSMENT",
    "Unsafe Transport": "HARASSMENT",
    "Harassment Near Schools": "HARASSMENT",
    "Harassment Near Colleges": "HARASSMENT",
    "Harassment Near Hostels": "HARASSMENT",
    "Harassment Near Workplaces": "HARASSMENT",
}


def get_recency_multiplier(days_old: Optional[int]) -> float:
    """Return recency multiplier based on how many days old an incident is."""
    if days_old is None:
        return 0.3
    for max_days, multiplier in RECENCY_MULTIPLIERS:
        if max_days is None:
            return multiplier
        if days_old <= max_days:
            return multiplier
    return 0.2


def is_women_safety_category(category: str) -> bool:
    """Check if a category is a valid women-safety category."""
    return category in WOMEN_SAFETY_CATEGORIES


def is_women_safety_incident(incident_dict: dict) -> bool:
    """Check if an incident dict has a valid women_safety_category in metadata."""
    meta = incident_dict.get("metadata") or incident_dict.get("meta_data") or {}
    if isinstance(meta, dict):
        ws_cat = meta.get("women_safety_category")
        if ws_cat and ws_cat in WOMEN_SAFETY_CATEGORIES:
            return True
    return False


def get_women_safety_details(category: str) -> Tuple[int, int, int, str]:
    """Return (tier, risk_weight, severity_weight, base_severity) for a category."""
    return WOMEN_SAFETY_CATEGORIES.get(category, (3, 20, 20, "LOW"))
