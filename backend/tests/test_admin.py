import uuid
from datetime import datetime

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.incident import Incident, IncidentType, IncidentSeverity, IncidentSource, IncidentStatus
from app.models.user import User, UserRole


@pytest.mark.asyncio
@pytest.mark.admin
async def test_get_dashboard_stats(async_client: AsyncClient, admin_headers):
    response = await async_client.get("/api/v1/admin/dashboard", headers=admin_headers)
    assert response.status_code == 200
    data = response.json()
    assert "total_incidents" in data
    assert "active_users" in data
    assert "sos_events" in data
    assert "verified_reports" in data
    assert "incidents_by_district" in data
    assert "incidents_by_type" in data
    assert "risk_trend" in data
    assert "incidents_trend" in data
    assert "recent_alerts" in data


@pytest.mark.asyncio
@pytest.mark.admin
async def test_list_incidents_moderation(async_client: AsyncClient, admin_headers):
    response = await async_client.get("/api/v1/admin/incidents", headers=admin_headers)
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data
    assert "page" in data
    assert "page_size" in data


@pytest.mark.asyncio
@pytest.mark.admin
async def test_moderate_incident(async_client: AsyncClient, admin_headers, sample_incident):
    payload = {
        "incident_id": str(sample_incident.id),
        "status": "verified",
        "moderation_notes": "Approved after review",
    }
    response = await async_client.put(
        f"/api/v1/admin/incidents/{sample_incident.id}/moderate",
        json=payload,
        headers=admin_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "verified"
    assert data["moderation_notes"] == "Approved after review"


@pytest.mark.asyncio
@pytest.mark.admin
async def test_moderate_incident_approve(async_client: AsyncClient, admin_headers, sample_incident):
    payload = {
        "incident_id": str(sample_incident.id),
        "status": "verified",
    }
    response = await async_client.put(
        f"/api/v1/admin/incidents/{sample_incident.id}/moderate",
        json=payload,
        headers=admin_headers,
    )
    assert response.status_code == 200
    assert response.json()["status"] == "verified"


@pytest.mark.asyncio
@pytest.mark.admin
async def test_moderate_incident_reject(async_client: AsyncClient, admin_headers, sample_incident):
    payload = {
        "incident_id": str(sample_incident.id),
        "status": "dismissed",
        "moderation_notes": "False report",
    }
    response = await async_client.put(
        f"/api/v1/admin/incidents/{sample_incident.id}/moderate",
        json=payload,
        headers=admin_headers,
    )
    assert response.status_code == 200
    assert response.json()["status"] == "dismissed"


@pytest.mark.asyncio
@pytest.mark.admin
async def test_moderate_incident_not_found(async_client: AsyncClient, admin_headers):
    fake_id = uuid.uuid4()
    payload = {"incident_id": str(fake_id), "status": "verified"}
    response = await async_client.put(
        f"/api/v1/admin/incidents/{fake_id}/moderate",
        json=payload,
        headers=admin_headers,
    )
    assert response.status_code == 404


@pytest.mark.asyncio
@pytest.mark.admin
async def test_moderate_incident_invalid_status(async_client: AsyncClient, admin_headers, sample_incident):
    payload = {
        "incident_id": str(sample_incident.id),
        "status": "invalid_status",
    }
    response = await async_client.put(
        f"/api/v1/admin/incidents/{sample_incident.id}/moderate",
        json=payload,
        headers=admin_headers,
    )
    assert response.status_code == 400


@pytest.mark.asyncio
@pytest.mark.admin
async def test_list_users(async_client: AsyncClient, admin_headers):
    response = await async_client.get("/api/v1/admin/users", headers=admin_headers)
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data
    if data["items"]:
        user = data["items"][0]
        assert "id" in user
        assert "email" in user
        assert "role" in user
        assert "is_active" in user
        assert "total_reports" in user


@pytest.mark.asyncio
@pytest.mark.admin
async def test_change_user_role(async_client: AsyncClient, admin_headers, test_user):
    response = await async_client.put(
        f"/api/v1/admin/users/{test_user.id}/role?role=moderator",
        headers=admin_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["role"] == "moderator"


@pytest.mark.asyncio
@pytest.mark.admin
async def test_change_user_role_invalid(async_client: AsyncClient, admin_headers, test_user):
    response = await async_client.put(
        f"/api/v1/admin/users/{test_user.id}/role?role=superadmin",
        headers=admin_headers,
    )
    assert response.status_code == 400


@pytest.mark.asyncio
@pytest.mark.admin
async def test_change_user_role_not_found(async_client: AsyncClient, admin_headers):
    fake_id = uuid.uuid4()
    response = await async_client.put(
        f"/api/v1/admin/users/{fake_id}/role?role=moderator",
        headers=admin_headers,
    )
    assert response.status_code == 404


@pytest.mark.asyncio
@pytest.mark.admin
async def test_change_user_status(async_client: AsyncClient, admin_headers, test_user):
    response = await async_client.put(
        f"/api/v1/admin/users/{test_user.id}/status?is_active=false",
        headers=admin_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["is_active"] is False


@pytest.mark.asyncio
@pytest.mark.admin
async def test_change_user_status_not_found(async_client: AsyncClient, admin_headers):
    fake_id = uuid.uuid4()
    response = await async_client.put(
        f"/api/v1/admin/users/{fake_id}/status?is_active=false",
        headers=admin_headers,
    )
    assert response.status_code == 404


@pytest.mark.asyncio
@pytest.mark.admin
async def test_get_agent_status(async_client: AsyncClient, admin_headers):
    response = await async_client.get("/api/v1/admin/agents/status", headers=admin_headers)
    assert response.status_code == 200
    data = response.json()
    assert "agents" in data
    assert "pipeline" in data
    assert len(data["agents"]) >= 4
    for agent in data["agents"]:
        assert "name" in agent
        assert "status" in agent


@pytest.mark.asyncio
@pytest.mark.admin
async def test_non_admin_access(async_client: AsyncClient, auth_headers):
    admin_endpoints = [
        ("GET", "/api/v1/admin/dashboard"),
        ("GET", "/api/v1/admin/incidents"),
        ("GET", "/api/v1/admin/users"),
        ("GET", "/api/v1/admin/agents/status"),
    ]
    for method, url in admin_endpoints:
        if method == "GET":
            response = await async_client.get(url, headers=auth_headers)
        else:
            response = await async_client.post(url, headers=auth_headers, json={})
        assert response.status_code == 403, (
            f"Expected 403 for {method} {url}, got {response.status_code}"
        )
