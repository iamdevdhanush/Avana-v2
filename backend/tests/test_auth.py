import uuid
from datetime import datetime
from unittest.mock import patch

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select

from app.models.user import User, UserRole, EmergencyContact
from app.schemas.auth import AuthResponse, UserResponse


@pytest.mark.asyncio
@pytest.mark.auth
async def test_signup_success(async_client: AsyncClient, db_session):
    payload = {
        "email": "newuser@example.com",
        "password": "securepassword123",
        "name": "New User",
    }
    response = await async_client.post("/api/v1/auth/signup", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["access_token"] is not None
    assert data["token_type"] == "bearer"
    assert data["user"]["email"] == "newuser@example.com"
    assert data["user"]["name"] == "New User"
    assert data["user"]["role"] == "user"
    assert data["user"]["is_verified"] is False
    assert "id" in data["user"]
    assert "created_at" in data["user"]

    result = await db_session.execute(select(User).where(User.email == "newuser@example.com"))
    user = result.scalar_one_or_none()
    assert user is not None
    assert user.name == "New User"


@pytest.mark.asyncio
@pytest.mark.auth
async def test_signup_duplicate_email(async_client: AsyncClient, test_user):
    payload = {
        "email": test_user.email,
        "password": "securepassword123",
        "name": "Duplicate User",
    }
    response = await async_client.post("/api/v1/auth/signup", json=payload)
    assert response.status_code == 409
    data = response.json()
    assert "detail" in data
    assert "already registered" in data["detail"].lower()


@pytest.mark.asyncio
@pytest.mark.auth
async def test_login_success(async_client: AsyncClient, test_user):
    payload = {
        "email": test_user.email,
        "password": "anypassword",
    }
    response = await async_client.post("/api/v1/auth/login", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["access_token"] is not None
    assert data["token_type"] == "bearer"
    assert data["user"]["email"] == test_user.email
    assert data["user"]["name"] == test_user.name


@pytest.mark.asyncio
@pytest.mark.auth
async def test_login_invalid_credentials(async_client: AsyncClient):
    payload = {
        "email": "nonexistent@example.com",
        "password": "wrongpassword",
    }
    response = await async_client.post("/api/v1/auth/login", json=payload)
    assert response.status_code == 401
    data = response.json()
    assert "detail" in data
    assert "invalid" in data["detail"].lower()


@pytest.mark.asyncio
@pytest.mark.auth
async def test_login_unverified_email(async_client: AsyncClient, db_session, test_user):
    test_user.is_verified = False
    await db_session.flush()
    payload = {
        "email": test_user.email,
        "password": "anypassword",
    }
    response = await async_client.post("/api/v1/auth/login", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["access_token"] is not None


@pytest.mark.asyncio
@pytest.mark.auth
async def test_get_current_user(async_client: AsyncClient, auth_headers):
    response = await async_client.get("/api/v1/auth/me", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "testuser@example.com"
    assert data["name"] == "Test User"
    assert data["role"] == "user"
    assert "id" in data


@pytest.mark.asyncio
@pytest.mark.auth
async def test_update_profile(async_client: AsyncClient, auth_headers):
    payload = {"name": "Updated Name", "phone": "+919999999999"}
    response = await async_client.put("/api/v1/auth/me", json=payload, headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Updated Name"


@pytest.mark.asyncio
@pytest.mark.auth
async def test_add_emergency_contact(async_client: AsyncClient, auth_headers):
    payload = {
        "name": "Emergency Contact",
        "phone": "+919876543210",
        "relationship": "family",
        "is_primary": True,
    }
    response = await async_client.post(
        "/api/v1/auth/emergency-contacts", json=payload, headers=auth_headers
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Emergency Contact"
    assert data["phone"] == "+919876543210"
    assert data["relationship"] == "family"
    assert data["is_primary"] is True
    assert "id" in data


@pytest.mark.asyncio
@pytest.mark.auth
async def test_list_emergency_contacts(
    async_client: AsyncClient, auth_headers, db_session, test_user
):
    contact1 = EmergencyContact(
        id=uuid.uuid4(),
        user_id=test_user.id,
        name="Contact One",
        phone="+911111111111",
        relationship="friend",
        is_primary=True,
    )
    contact2 = EmergencyContact(
        id=uuid.uuid4(),
        user_id=test_user.id,
        name="Contact Two",
        phone="+912222222222",
        relationship="family",
        is_primary=False,
    )
    db_session.add_all([contact1, contact2])
    await db_session.flush()

    response = await async_client.get("/api/v1/auth/emergency-contacts", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 2
    names = [c["name"] for c in data]
    assert "Contact One" in names
    assert "Contact Two" in names


@pytest.mark.asyncio
@pytest.mark.auth
async def test_delete_emergency_contact(
    async_client: AsyncClient, auth_headers, db_session, test_user
):
    contact = EmergencyContact(
        id=uuid.uuid4(),
        user_id=test_user.id,
        name="Delete Contact",
        phone="+913333333333",
        relationship="other",
        is_primary=False,
    )
    db_session.add(contact)
    await db_session.flush()

    response = await async_client.delete(
        f"/api/v1/auth/emergency-contacts/{contact.id}", headers=auth_headers
    )
    assert response.status_code == 200
    data = response.json()
    assert "deleted" in data["message"].lower()

    result = await db_session.execute(
        select(EmergencyContact).where(EmergencyContact.id == contact.id)
    )
    assert result.scalar_one_or_none() is None


@pytest.mark.asyncio
@pytest.mark.auth
async def test_unauthenticated_access(async_client: AsyncClient):
    endpoints = [
        ("GET", "/api/v1/auth/me"),
        ("PUT", "/api/v1/auth/me"),
        ("GET", "/api/v1/auth/emergency-contacts"),
        ("POST", "/api/v1/auth/emergency-contacts"),
    ]
    for method, url in endpoints:
        if method == "GET":
            response = await async_client.get(url)
        else:
            response = await async_client.put(url, json={"name": "test"})
        assert response.status_code == 403 or response.status_code == 401, (
            f"Expected 401/403 for {method} {url}, got {response.status_code}"
        )
