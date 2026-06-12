"""
Mock intelligence data provider.

When MOCK_INTELLIGENCE_MODE=true, replaces Gemini extraction with
5 realistic incident objects to exercise the full pipeline:
  fetch → dedup → geocode → save → risk → heatmap

Production behavior is unchanged unless the env var is set.
"""

import logging
from typing import List

logger = logging.getLogger(__name__)

_MOCK_INCIDENTS: List[dict] = [
    {
        "incident_type": "harassment",
        "severity": "high",
        "location": "City Bus Stand, Mysuru",
        "city": "Mysuru",
        "district": "Mysuru",
        "description": "Harassment reported near city bus stand during evening hours. Multiple commuters affected near platform 3.",
        "confidence": 0.91,
        "source_url": "https://mock-source.local/mysuru-harassment-001",
        "article_title": "Harassment reported near city bus stand",
    },
    {
        "incident_type": "theft",
        "severity": "medium",
        "location": "KR Market, Bengaluru",
        "city": "Bengaluru",
        "district": "Bengaluru Urban",
        "description": "Chain snatching incident at KR Market. Victim reported loss of gold jewelry worth 2 lakhs.",
        "confidence": 0.85,
        "source_url": "https://mock-source.local/bengaluru-theft-002",
        "article_title": "Chain snatching at KR Market",
    },
    {
        "incident_type": "assault",
        "severity": "critical",
        "location": "Kengeri, Bengaluru",
        "city": "Bengaluru",
        "district": "Bengaluru Urban",
        "description": "Group assault reported near Kengeri railway station. Victim rushed to hospital with serious injuries.",
        "confidence": 0.93,
        "source_url": "https://mock-source.local/bengaluru-assault-003",
        "article_title": "Assault near Kengeri railway station",
    },
    {
        "incident_type": "traffic_accident",
        "severity": "high",
        "location": "Mangaluru City Center",
        "city": "Mangaluru",
        "district": "Dakshina Kannada",
        "description": "Major traffic accident at Mangaluru city center involving auto-rickshaw and motorcycle. Two persons injured.",
        "confidence": 0.88,
        "source_url": "https://mock-source.local/mangaluru-accident-004",
        "article_title": "Traffic accident at Mangaluru City Center",
    },
    {
        "incident_type": "burglary",
        "severity": "medium",
        "location": "Jayanagar, Bengaluru",
        "city": "Bengaluru",
        "district": "Bengaluru Urban",
        "description": "House burglary reported in Jayanagar 4th Block. Cash and electronics stolen from locked residence.",
        "confidence": 0.79,
        "source_url": "https://mock-source.local/bengaluru-burglary-005",
        "article_title": "Burglary in Jayanagar 4th Block",
    },
]


def get_mock_incidents() -> List[dict]:
    logger.info(f"Returning {len(_MOCK_INCIDENTS)} mock incidents (MOCK_INTELLIGENCE_MODE)")
    return [dict(inc) for inc in _MOCK_INCIDENTS]
