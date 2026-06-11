from unittest.mock import patch

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
@pytest.mark.risk
async def test_calculate_risk_score(async_client: AsyncClient, auth_headers):
    payload = {"latitude": 12.9716, "longitude": 77.5946}
    with patch("app.api.v1.risk.score_location") as mock_run:
        mock_run.return_value = {
            "score": 35.5,
            "category": "Moderate",
            "factors": {
                "historical_risk": 20.0,
                "recent_impact": 5.0,
                "night_penalty": 0.0,
                "severity_penalty": 10.0,
                "nearby_police_stations": 2,
                "nearby_hospitals": 1,
            },
        }
        response = await async_client.post("/api/v1/risk/score", json=payload, headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["score"] == 35.5
        assert data["category"] == "Moderate"
        assert "factors" in data
        assert "recommendations" in data


@pytest.mark.asyncio
@pytest.mark.risk
async def test_calculate_risk_score_outside_karnataka(async_client: AsyncClient, auth_headers):
    payload = {"latitude": 28.6139, "longitude": 77.2090}
    with patch("app.api.v1.risk.score_location") as mock_run:
        mock_run.return_value = {
            "score": 50.0,
            "category": "Moderate",
            "factors": {
                "historical_risk": 0.0,
                "recent_impact": 0.0,
                "night_penalty": 0.0,
                "severity_penalty": 0.0,
                "nearby_police_stations": 0,
                "nearby_hospitals": 0,
            },
        }
        response = await async_client.post("/api/v1/risk/score", json=payload, headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data["score"], float)


@pytest.mark.asyncio
@pytest.mark.risk
async def test_get_heatmap_data(async_client: AsyncClient):
    payload = {
        "sw_lat": 12.8,
        "sw_lng": 77.4,
        "ne_lat": 13.2,
        "ne_lng": 77.8,
        "zoom": 12,
    }
    with patch("app.api.v1.risk.get_heatmap_data") as mock_heatmap:
        mock_heatmap.return_value = [
            {"latitude": 12.97, "longitude": 77.59, "score": 30.0, "category": "Safe"},
            {"latitude": 12.98, "longitude": 77.60, "score": 55.0, "category": "Moderate"},
        ]
        response = await async_client.post("/api/v1/risk/heatmap", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "points" in data
        assert "generated_at" in data
        assert "district_summaries" in data
        assert len(data["points"]) == 2
        assert data["points"][0]["weight"] == 0.3
        assert data["points"][1]["weight"] == 0.55


@pytest.mark.asyncio
@pytest.mark.risk
async def test_get_heatmap_data_invalid_bounds(async_client: AsyncClient):
    payload = {
        "sw_lat": 90.0,
        "sw_lng": 180.0,
        "ne_lat": -90.0,
        "ne_lng": -180.0,
        "zoom": 10,
    }
    with patch("app.api.v1.risk.get_heatmap_data") as mock_heatmap:
        mock_heatmap.return_value = []
        response = await async_client.post("/api/v1/risk/heatmap", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert len(data["points"]) == 0


@pytest.mark.asyncio
@pytest.mark.risk
async def test_get_district_risk_summary(async_client: AsyncClient, db_session, sample_incident):
    response = await async_client.get(f"/api/v1/risk/district/{sample_incident.district}")
    assert response.status_code == 200
    data = response.json()
    assert data["district"] == sample_incident.district
    assert "risk_score" in data
    assert "risk_category" in data
    assert "total_incidents" in data
    assert "high_risk_incidents" in data
    assert "medium_risk_incidents" in data
    assert "low_risk_incidents" in data
    assert "generated_at" in data


@pytest.mark.asyncio
@pytest.mark.risk
async def test_get_district_risk_summary_not_found(async_client: AsyncClient):
    response = await async_client.get("/api/v1/risk/district/NonExistentDistrict")
    assert response.status_code == 404
    data = response.json()
    assert "no data found" in data["detail"].lower()
