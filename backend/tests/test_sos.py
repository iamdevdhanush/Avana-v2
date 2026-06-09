import uuid
from datetime import datetime

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.sos_event import SOSEvent, SOSStatus


@pytest.mark.asyncio
@pytest.mark.sos
async def test_trigger_sos(async_client: AsyncClient):
    payload = {
        "latitude": 12.9716,
        "longitude": 77.5946,
        "message": "Help! I am in danger.",
    }
    response = await async_client.post("/api/v1/sos", json=payload)
    assert response.status_code == 403 or response.status_code == 401


@pytest.mark.asyncio
@pytest.mark.sos
async def test_trigger_sos_authenticated(async_client: AsyncClient, auth_headers):
    payload = {
        "latitude": 12.9716,
        "longitude": 77.5946,
        "message": "Help! I am in danger.",
        "emergency_type": "general",
    }
    response = await async_client.post("/api/v1/sos", json=payload, headers=auth_headers)
    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "triggered"
    assert data["message"] == "Help! I am in danger."
    assert "id" in data
    assert "created_at" in data
    assert data["notified_contacts"] is not None


@pytest.mark.asyncio
@pytest.mark.sos
async def test_trigger_sos_missing_location(async_client: AsyncClient, auth_headers):
    payload = {"message": "Help!"}
    response = await async_client.post("/api/v1/sos", json=payload, headers=auth_headers)
    assert response.status_code == 422


@pytest.mark.asyncio
@pytest.mark.sos
async def test_get_sos_history(async_client: AsyncClient, auth_headers, db_session, test_user):
    for i in range(3):
        sos = SOSEvent(
            id=uuid.uuid4(),
            user_id=test_user.id,
            latitude=12.9716,
            longitude=77.5946,
            geom=None,
            message=f"SOS event {i}",
            status=SOSStatus.TRIGGERED,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db_session.add(sos)
    await db_session.flush()

    response = await async_client.get("/api/v1/sos/history", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 3
    for event in data:
        assert "status" in event
        assert "created_at" in event


@pytest.mark.asyncio
@pytest.mark.sos
async def test_get_sos_history_empty(async_client: AsyncClient, auth_headers):
    response = await async_client.get("/api/v1/sos/history", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data == []


@pytest.mark.asyncio
@pytest.mark.sos
async def test_get_sos_detail(async_client: AsyncClient, auth_headers, sample_sos):
    response = await async_client.get(f"/api/v1/sos/{sample_sos.id}", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(sample_sos.id)
    assert data["status"] == "triggered"
    assert data["message"] == sample_sos.message


@pytest.mark.asyncio
@pytest.mark.sos
async def test_get_sos_detail_not_found(async_client: AsyncClient, auth_headers):
    fake_id = uuid.uuid4()
    response = await async_client.get(f"/api/v1/sos/{fake_id}", headers=auth_headers)
    assert response.status_code == 404
    data = response.json()
    assert "not found" in data["detail"].lower()
