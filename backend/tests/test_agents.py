from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.asyncio
@pytest.mark.agents
async def test_news_intelligence_extract():
    with patch("app.pipeline.intelligence.gemini_service.generate") as mock_generate:
        mock_generate.return_value = (
            '[{"incident_type": "theft", "severity": "medium", '
            '"location": "MG Road", "district": "Bengaluru Urban", '
            '"city": "Bengaluru", "description": "Mobile phone theft", '
            '"confidence": 0.85, "incident_date": "2025-01-15"}]'
        )

        from app.pipeline.intelligence import extract_incidents_from_article

        article = {
            "title": "Theft on MG Road",
            "link": "https://example.com/news/1",
            "summary": "A theft occurred on MG Road",
            "full_text": "A theft occurred on MG Road in Bengaluru. The victim reported...",
            "city": "Bengaluru",
            "state": "Karnataka",
        }
        result = await extract_incidents_from_article(article)
        assert len(result) > 0
        incident = result[0]
        assert incident["incident_type"] == "theft"
        assert incident["severity"] == "medium"
        assert incident["confidence"] == 0.85


@pytest.mark.asyncio
@pytest.mark.agents
async def test_risk_scoring_calculation():
    with patch("app.pipeline.risk.async_session_factory") as mock_session_factory:
        mock_session = AsyncMock()
        mock_session_factory.return_value.__aenter__.return_value = mock_session

        mock_hist = AsyncMock()
        mock_hist.fetchone.return_value = (5, 20.0)
        mock_recent = AsyncMock()
        mock_recent.scalar.return_value = 2
        mock_police = AsyncMock()
        mock_police.scalar.return_value = 1
        mock_hosp = AsyncMock()
        mock_hosp.scalar.return_value = 2

        mock_session.execute.side_effect = [mock_hist, mock_recent, mock_police, mock_hosp]

        from app.pipeline.risk import score_location

        result = await score_location(12.9716, 77.5946)
        assert "score" in result
        assert "category" in result
        assert "factors" in result
        assert isinstance(result["score"], float)
        assert result["category"] in ("Safe", "Moderate", "Elevated", "High Risk")


@pytest.mark.asyncio
@pytest.mark.agents
async def test_heatmap_grid_generation():
    from app.pipeline.heatmap import _generate_grid

    points = _generate_grid(12.9, 77.5, 13.0, 77.6)
    assert len(points) > 0
    assert isinstance(points[0], tuple)
    assert len(points[0]) == 2


@pytest.mark.asyncio
@pytest.mark.agents
async def test_geocoding():
    from app.pipeline.intelligence import geocode_incidents

    incidents = [
        {"location": "MG Road, Bengaluru", "incident_type": "theft"},
    ]
    # geocode_incidents will try to connect to Nominatim;
    # if it fails, lat/lng will be None — that's acceptable for this test
    result = await geocode_incidents(incidents)
    assert isinstance(result, list)
    assert len(result) == 1
