from unittest.mock import patch

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
@pytest.mark.route
async def test_get_safe_route(async_client: AsyncClient, auth_headers):
    payload = {
        "source_lat": 12.9716,
        "source_lng": 77.5946,
        "dest_lat": 12.9344,
        "dest_lng": 77.6101,
    }
    with patch("app.api.v1.route.route_run") as mock_route:
        mock_route.return_value = {
            "safest_route": {
                "profile": "driving",
                "distance_meters": 5000,
                "duration_seconds": 600,
                "avg_safety_score": 85.0,
                "min_safety_score": 70.0,
                "segments": [
                    {
                        "start": [12.9716, 77.5946],
                        "end": [12.9344, 77.6101],
                        "score": 85.0,
                        "risk_category": "Safe",
                        "length_meters": 5000,
                    }
                ],
            },
            "fastest_route": {
                "profile": "driving",
                "distance_meters": 4800,
                "duration_seconds": 540,
                "avg_safety_score": 65.0,
                "segments": [
                    {
                        "start": [12.9716, 77.5946],
                        "end": [12.9344, 77.6101],
                        "score": 65.0,
                        "risk_category": "Moderate",
                        "length_meters": 4800,
                    }
                ],
            },
            "balanced_route": {
                "profile": "driving",
                "distance_meters": 4900,
                "duration_seconds": 570,
                "avg_safety_score": 75.0,
                "segments": [
                    {
                        "start": [12.9716, 77.5946],
                        "end": [12.9344, 77.6101],
                        "score": 75.0,
                        "risk_category": "Safe",
                        "length_meters": 4900,
                    }
                ],
            },
        }
        response = await async_client.post("/api/v1/route/safe", json=payload, headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "source" in data
        assert "destination" in data
        assert "safest" in data
        assert "fastest" in data
        assert "balanced" in data
        assert data["safest"]["safety_score"] == 85.0
        assert data["safest"]["duration_minutes"] == 10.0
        assert data["safest"]["distance_km"] == 5.0


@pytest.mark.asyncio
@pytest.mark.route
async def test_get_safe_route_same_point(async_client: AsyncClient, auth_headers):
    payload = {
        "source_lat": 12.9716,
        "source_lng": 77.5946,
        "dest_lat": 12.9716,
        "dest_lng": 77.5946,
    }
    with patch("app.api.v1.route.route_run") as mock_route:
        mock_route.return_value = {
            "safest_route": {
                "profile": "driving",
                "distance_meters": 0,
                "duration_seconds": 0,
                "avg_safety_score": 100.0,
                "min_safety_score": 100.0,
                "segments": [],
            },
            "fastest_route": {
                "profile": "driving",
                "distance_meters": 0,
                "duration_seconds": 0,
                "avg_safety_score": 100.0,
                "segments": [],
            },
            "balanced_route": {
                "profile": "driving",
                "distance_meters": 0,
                "duration_seconds": 0,
                "avg_safety_score": 100.0,
                "segments": [],
            },
        }
        response = await async_client.post("/api/v1/route/safe", json=payload, headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["safest"]["distance_km"] == 0
        assert data["safest"]["duration_minutes"] == 0


@pytest.mark.asyncio
@pytest.mark.route
async def test_get_safe_route_invalid_coords(async_client: AsyncClient, auth_headers):
    payload = {
        "source_lat": 200.0,
        "source_lng": 400.0,
        "dest_lat": 12.9344,
        "dest_lng": 77.6101,
    }
    with patch("app.api.v1.route.route_run") as mock_route:
        mock_route.return_value = {
            "safest_route": None,
            "fastest_route": None,
            "balanced_route": None,
        }
        response = await async_client.post("/api/v1/route/safe", json=payload, headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["safest"]["safety_score"] == 0


@pytest.mark.asyncio
@pytest.mark.route
async def test_route_health(async_client: AsyncClient):
    response = await async_client.get("/api/v1/route/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "Route Intelligence"
