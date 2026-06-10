from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio


@pytest.mark.asyncio
@pytest.mark.agents
async def test_news_intelligence_extract():
    with patch("app.agents.news_intelligence.gemini_service.generate") as mock_generate:
        mock_generate.return_value = (
            '[{"incident_type": "theft", "severity": "medium", '
            '"location": "MG Road", "district": "Bengaluru Urban", '
            '"city": "Bengaluru", "description": "Mobile phone theft", '
            '"confidence": 0.85, "incident_date": "2025-01-15"}]'
        )

        from app.agents.news_intelligence import extract_incidents

        state = {
            "articles": [
                {
                    "title": "Theft on MG Road",
                    "link": "https://example.com/news/1",
                    "summary": "A theft occurred on MG Road",
                    "full_text": "A theft occurred on MG Road in Bengaluru. The victim reported...",
                    "city": "Bengaluru",
                    "state": "Karnataka",
                }
            ],
            "extracted_incidents": [],
            "geocoded_incidents": [],
            "saved_count": 0,
            "errors": [],
            "sources": [],
        }
        result = await extract_incidents(state)
        assert "extracted_incidents" in result
        assert len(result["extracted_incidents"]) > 0
        incident = result["extracted_incidents"][0]
        assert incident["incident_type"] == "theft"
        assert incident["severity"] == "medium"
        assert incident["confidence"] == 0.85


@pytest.mark.asyncio
@pytest.mark.agents
async def test_community_intelligence_classify():
    with patch("app.agents.community_intelligence.gemini_service.generate") as mock_generate:
        mock_generate.return_value = (
            '{"validated_type": "harassment", "validated_severity": "high", '
            '"location_coherent": true, "description_valid": true, '
            '"confidence_adjustment": 0.1, "notes": "Valid report"}'
        )

        from app.agents.community_intelligence import classify_report

        state = {
            "pending_reports": [
                {
                    "id": "123",
                    "user_id": "456",
                    "incident_type": "harassment",
                    "severity": "high",
                    "latitude": 12.9716,
                    "longitude": 77.5946,
                    "description": "Harassment reported near bus stop",
                    "status": "pending",
                    "confidence_score": 0.7,
                    "reporter_ip": "192.168.1.1",
                    "created_at": "2025-01-15T10:00:00",
                    "source": "mobile_app",
                }
            ],
            "classified_reports": [],
            "duplicates_found": [],
            "spam_detected": [],
            "verified_reports": [],
            "saved_count": 0,
            "errors": [],
        }
        result = await classify_report(state)
        assert "classified_reports" in result
        assert len(result["classified_reports"]) == 1
        report = result["classified_reports"][0]
        assert report["validated_type"] == "harassment"
        assert report["validated_severity"] == "high"
        assert report["confidence_adjustment"] == 0.1


@pytest.mark.asyncio
@pytest.mark.agents
async def test_geocoding_agent():
    with patch("app.agents.geocoding.nominatim_service.geocode", new_callable=AsyncMock) as mock_geocode:
        mock_geocode.return_value = {
            "lat": 12.9716,
            "lng": 77.5946,
            "display_name": "MG Road, Bengaluru, Karnataka, India",
            "place_id": "12345",
        }

        from app.agents.geocoding import geocode_query

        state = {"query": "MG Road", "result": None, "cached": False, "error": None}
        result = await geocode_query(state)
        assert "result" in result
        assert result["result"]["lat"] == 12.9716
        assert result["result"]["lng"] == 77.5946


@pytest.mark.asyncio
@pytest.mark.agents
async def test_geocoding_agent_cached():
    from app.agents.geocoding import geocode_query

    state = {"query": "MG Road", "result": {"latitude": 12.9716}, "cached": True, "error": None}
    result = await geocode_query(state)
    assert result == {}


@pytest.mark.asyncio
@pytest.mark.agents
async def test_risk_scoring_calculation():
    with patch("app.agents.risk_scoring.async_session_factory") as mock_session_factory:
        mock_session = AsyncMock()
        mock_session_factory.return_value.__aenter__.return_value = mock_session

        mock_result = AsyncMock()
        mock_result.fetchone.return_value = (5, 20.0)
        mock_result2 = AsyncMock()
        mock_result2.fetchone.return_value = (2,)
        mock_result3 = AsyncMock()
        mock_result3.fetchone.return_value = (1,)
        mock_result4 = AsyncMock()
        mock_result4.fetchone.return_value = (2,)
        mock_result5 = AsyncMock()
        mock_result5.fetchone.return_value = ("Bengaluru Urban",)

        mock_session.execute.side_effect = [
            mock_result,
            mock_result2,
            mock_result3,
            mock_result4,
            mock_result5,
        ]

        from app.agents.risk_scoring import run

        result = await run(12.9716, 77.5946)
        assert "score" in result
        assert "category" in result
        assert "factors" in result
        assert isinstance(result["score"], float)
        assert result["category"] in ("Safe", "Moderate", "High Risk", "Critical")


@pytest.mark.asyncio
@pytest.mark.agents
async def test_heatmap_grid_generation():
    from app.agents.heatmap import determine_grid

    state = {
        "zoom_level": "city",
        "district": None,
        "city": "Bengaluru",
        "grid_points": [],
        "heatmap_data": [],
        "generated_at": "",
        "errors": [],
    }
    result = await determine_grid(state)
    assert "grid_points" in result
    assert len(result["grid_points"]) > 0
    point = result["grid_points"][0]
    assert "latitude" in point
    assert "longitude" in point


@pytest.mark.asyncio
@pytest.mark.agents
async def test_route_intelligence_scoring():
    from app.agents.route_intelligence import _decode_polyline, _interpolate_segments

    coords = [(12.9716, 77.5946), (12.9720, 77.5950), (12.9725, 77.5955), (12.9730, 77.5960)]
    segments = _interpolate_segments(coords, interval_meters=10)
    assert isinstance(segments, list)
    if segments:
        seg = segments[0]
        assert "start" in seg
        assert "end" in seg
        assert "midpoint" in seg
        assert "length_meters" in seg


@pytest.mark.asyncio
@pytest.mark.agents
async def test_recommendation_generation():
    from app.agents.safety_recommendation import _fallback_recommendations

    context = {
        "risk_score": 75.0,
        "risk_category": "High Risk",
        "current_hour": 22,
        "is_night": True,
        "nearby_incidents": [{"type": "theft", "severity": "medium", "description": "Theft", "distance_meters": 500}],
        "nearby_police": [],
        "nearby_hospitals": [],
        "user_history": [],
    }
    recommendations = _fallback_recommendations(context)
    assert isinstance(recommendations, list)
    assert len(recommendations) > 0
    for rec in recommendations:
        assert "title" in rec
        assert "description" in rec
        assert "priority" in rec
        assert "category" in rec


@pytest.mark.asyncio
@pytest.mark.agents
async def test_recommendation_safe_area():
    from app.agents.safety_recommendation import _fallback_recommendations

    context = {
        "risk_score": 15.0,
        "risk_category": "Safe",
        "current_hour": 14,
        "is_night": False,
        "nearby_incidents": [],
        "nearby_police": [{"name": "Police Station", "address": "Main Road", "distance_meters": 300}],
        "nearby_hospitals": [{"name": "Hospital", "address": "Nearby", "distance_meters": 500}],
        "user_history": [],
    }
    recommendations = _fallback_recommendations(context)
    assert isinstance(recommendations, list)
    safe_recs = [r for r in recommendations if "safe" in r.get("title", "").lower()]
    assert len(safe_recs) > 0
