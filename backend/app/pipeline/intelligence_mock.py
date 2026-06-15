"""
Mock intelligence data provider — Women's Safety Only.

When MOCK_INTELLIGENCE_MODE=true, replaces Gemini extraction with
5 women-safety-only incident objects to exercise the full pipeline:
  fetch → dedup → geocode → save → risk → heatmap

Every incident has a valid women_safety_category that gates it
into the risk/heatmap engine. Non-women-safety incidents are
never generated, even in mock mode.
"""

import logging
from typing import List

logger = logging.getLogger(__name__)

_MOCK_INCIDENTS: List[dict] = [
    {
        "incident_type": "sexual_assault",
        "severity": "critical",
        "women_safety_category": "Rape",
        "location": "Kengeri, Bengaluru",
        "city": "Bengaluru",
        "district": "Bengaluru Urban",
        "description": "Sexual assault reported near Kengeri railway station. Victim attacked in isolated area near platform 2 during evening hours.",
        "confidence": 0.93,
        "source_url": "https://mock-source.local/bengaluru-sexual-assault-001",
        "article_title": "Sexual assault near Kengeri railway station",
    },
    {
        "incident_type": "harassment",
        "severity": "high",
        "women_safety_category": "Molestation",
        "location": "City Bus Stand, Mysuru",
        "city": "Mysuru",
        "district": "Mysuru",
        "description": "Molestation reported near city bus stand during evening rush. Multiple female commuters affected near platform 3.",
        "confidence": 0.91,
        "source_url": "https://mock-source.local/mysuru-molestation-002",
        "article_title": "Molestation at City Bus Stand, Mysuru",
    },
    {
        "incident_type": "stalking",
        "severity": "high",
        "women_safety_category": "Stalking",
        "location": "KR Market, Bengaluru",
        "city": "Bengaluru",
        "district": "Bengaluru Urban",
        "description": "Woman stalked repeatedly near KR Market area over two weeks. Suspect identified from CCTV footage near vegetable market entrance.",
        "confidence": 0.85,
        "source_url": "https://mock-source.local/bengaluru-stalking-003",
        "article_title": "Stalking incident at KR Market",
    },
    {
        "incident_type": "domestic_violence",
        "severity": "high",
        "women_safety_category": "Domestic Violence",
        "location": "Mangaluru City Center",
        "city": "Mangaluru",
        "district": "Dakshina Kannada",
        "description": "Domestic violence complaint registered at Mangaluru women's police station. Victim reported repeated physical abuse by spouse.",
        "confidence": 0.88,
        "source_url": "https://mock-source.local/mangaluru-dv-004",
        "article_title": "Domestic violence case at Mangaluru",
    },
    {
        "incident_type": "assault",
        "severity": "critical",
        "women_safety_category": "Acid Attack",
        "location": "Jayanagar, Bengaluru",
        "city": "Bengaluru",
        "district": "Bengaluru Urban",
        "description": "Acid attack on woman in Jayanagar 4th Block. Victim attacked near bus stop, rushed to hospital with severe facial burns.",
        "confidence": 0.79,
        "source_url": "https://mock-source.local/bengaluru-acid-attack-005",
        "article_title": "Acid attack in Jayanagar 4th Block",
    },
]


def get_mock_incidents() -> List[dict]:
    logger.info(f"Returning {len(_MOCK_INCIDENTS)} women-safety-only mock incidents (MOCK_INTELLIGENCE_MODE)")
    return [dict(inc) for inc in _MOCK_INCIDENTS]
