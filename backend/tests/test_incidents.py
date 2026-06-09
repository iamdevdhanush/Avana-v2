import uuid
from datetime import datetime

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select

from app.models.incident import Incident, IncidentType, IncidentSeverity, IncidentSource, IncidentStatus


@pytest.mark.asyncio
@pytest.mark.incident
async def test_create_incident(async_client: AsyncClient, auth_headers):
    payload = {
        "incident_type": "theft",
        "severity": "medium",
        "latitude": 12.9716,
        "longitude": 77.5946,
        "description": "A theft occurred near the market",
        "title": "Market Theft",
        "district": "Bengaluru Urban",
        "city": "Bengaluru",
    }
    response = await async_client.post("/api/v1/incidents", json=payload, headers=auth_headers)
    assert response.status_code == 201
    data = response.json()
    assert data["incident_type"] == "theft"
    assert data["severity"] == "medium"
    assert data["latitude"] == 12.9716
    assert data["longitude"] == 77.5946
    assert data["description"] == "A theft occurred near the market"
    assert data["title"] == "Market Theft"
    assert data["district"] == "Bengaluru Urban"
    assert data["source"] == "user_report"
    assert data["status"] == "pending"
    assert "id" in data
    assert "created_at" in data


@pytest.mark.asyncio
@pytest.mark.incident
async def test_create_incident_anonymous(async_client: AsyncClient):
    payload = {
        "incident_type": "harassment",
        "severity": "high",
        "latitude": 12.9344,
        "longitude": 77.6101,
        "description": "Anonymous report of harassment",
        "title": "Anonymous Report",
        "district": "Bengaluru Urban",
        "city": "Bengaluru",
        "is_anonymous": True,
    }
    response = await async_client.post("/api/v1/incidents", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["incident_type"] == "harassment"
    assert data["severity"] == "high"
    assert data["source"] == "user_report"


@pytest.mark.asyncio
@pytest.mark.incident
async def test_create_incident_missing_fields(async_client: AsyncClient, auth_headers):
    payload = {
        "incident_type": "theft",
    }
    response = await async_client.post("/api/v1/incidents", json=payload, headers=auth_headers)
    assert response.status_code == 422
    data = response.json()
    assert "detail" in data


@pytest.mark.asyncio
@pytest.mark.incident
async def test_list_incidents(async_client: AsyncClient, db_session, test_user):
    for i in range(3):
        incident = Incident(
            id=uuid.uuid4(),
            incident_type=IncidentType.THEFT,
            severity=IncidentSeverity.MEDIUM,
            source=IncidentSource.USER_REPORT,
            status=IncidentStatus.PENDING,
            confidence_score=0.0,
            latitude=12.9716 + i * 0.01,
            longitude=77.5946 + i * 0.01,
            geom=None,
            description=f"Test incident {i}",
            title=f"Incident {i}",
            district="Bengaluru Urban",
            city="Bengaluru",
            user_id=test_user.id,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db_session.add(incident)
    await db_session.flush()

    response = await async_client.get("/api/v1/incidents")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 3
    assert len(data["items"]) >= 3
    assert "page" in data
    assert "page_size" in data


@pytest.mark.asyncio
@pytest.mark.incident
async def test_list_incidents_with_filters(async_client: AsyncClient, db_session, test_user):
    incident = Incident(
        id=uuid.uuid4(),
        incident_type=IncidentType.THEFT,
        severity=IncidentSeverity.HIGH,
        source=IncidentSource.USER_REPORT,
        status=IncidentStatus.PENDING,
        confidence_score=0.0,
        latitude=12.9716,
        longitude=77.5946,
        geom=None,
        description="High severity theft",
        title="High Theft",
        district="Bengaluru Urban",
        city="Bengaluru",
        user_id=test_user.id,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db_session.add(incident)
    await db_session.flush()

    response = await async_client.get(
        "/api/v1/incidents", params={"incident_type": "theft", "severity": "high", "district": "Bengaluru Urban"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1
    for item in data["items"]:
        assert item["incident_type"] == "theft"
        assert item["district"] == "Bengaluru Urban"


@pytest.mark.asyncio
@pytest.mark.incident
async def test_list_incidents_pagination(async_client: AsyncClient, db_session, test_user):
    for i in range(5):
        incident = Incident(
            id=uuid.uuid4(),
            incident_type=IncidentType.THEFT,
            severity=IncidentSeverity.LOW,
            source=IncidentSource.USER_REPORT,
            status=IncidentStatus.PENDING,
            confidence_score=0.0,
            latitude=12.9716,
            longitude=77.5946,
            geom=None,
            description=f"Pagination incident {i}",
            title=f"Page Incident {i}",
            district="Bengaluru Urban",
            city="Bengaluru",
            user_id=test_user.id,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db_session.add(incident)
    await db_session.flush()

    response = await async_client.get("/api/v1/incidents", params={"page": 1, "page_size": 3})
    assert response.status_code == 200
    data = response.json()
    assert data["page"] == 1
    assert data["page_size"] == 3
    assert len(data["items"]) <= 3


@pytest.mark.asyncio
@pytest.mark.incident
async def test_get_incident_detail(async_client: AsyncClient, sample_incident):
    response = await async_client.get(f"/api/v1/incidents/{sample_incident.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(sample_incident.id)
    assert data["incident_type"] == sample_incident.incident_type.value
    assert data["severity"] == sample_incident.severity.value
    assert data["description"] == sample_incident.description
    assert data["latitude"] == sample_incident.latitude


@pytest.mark.asyncio
@pytest.mark.incident
async def test_get_incident_not_found(async_client: AsyncClient):
    fake_id = uuid.uuid4()
    response = await async_client.get(f"/api/v1/incidents/{fake_id}")
    assert response.status_code == 404
    data = response.json()
    assert "not found" in data["detail"].lower()


@pytest.mark.asyncio
@pytest.mark.incident
async def test_get_nearby_incidents(async_client: AsyncClient, db_session, test_user):
    incident = Incident(
        id=uuid.uuid4(),
        incident_type=IncidentType.THEFT,
        severity=IncidentSeverity.LOW,
        source=IncidentSource.USER_REPORT,
        status=IncidentStatus.PENDING,
        confidence_score=0.0,
        latitude=12.9716,
        longitude=77.5946,
        geom=None,
        description="Nearby incident",
        title="Nearby",
        district="Bengaluru Urban",
        city="Bengaluru",
        user_id=test_user.id,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db_session.add(incident)
    await db_session.flush()

    response = await async_client.get(
        "/api/v1/incidents/nearby",
        params={"lat": 12.97, "lng": 77.59, "radius": 10, "limit": 10},
    )
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


@pytest.mark.asyncio
@pytest.mark.incident
async def test_get_nearby_incidents_no_location(async_client: AsyncClient):
    response = await async_client.get("/api/v1/incidents/nearby")
    assert response.status_code == 422


@pytest.mark.asyncio
@pytest.mark.incident
async def test_get_incident_stats(async_client: AsyncClient, db_session, test_user):
    for i in range(3):
        incident = Incident(
            id=uuid.uuid4(),
            incident_type=IncidentType.ASSAULT,
            severity=IncidentSeverity.HIGH,
            source=IncidentSource.USER_REPORT,
            status=IncidentStatus.PENDING,
            confidence_score=0.0,
            latitude=12.9716,
            longitude=77.5946,
            geom=None,
            description=f"Stats incident {i}",
            title=f"Stats {i}",
            district="Bengaluru Urban",
            city="Bengaluru",
            user_id=test_user.id,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db_session.add(incident)
    await db_session.flush()

    response = await async_client.get("/api/v1/incidents/stats")
    assert response.status_code == 200
    data = response.json()
    assert "total_incidents" in data
    assert "by_district" in data
    assert "by_type" in data
    assert isinstance(data["by_district"], list)
    assert isinstance(data["by_type"], list)
