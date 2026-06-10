import asyncio
import sys
import uuid
from datetime import datetime, timedelta
from typing import AsyncGenerator, Generator
from unittest.mock import AsyncMock, MagicMock, patch

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI
from jose import jwt
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import settings
from app.database import Base, get_db
from app.dependencies import get_current_user, require_user, require_admin
from app.main import app
from app.models.user import User, UserRole, EmergencyContact
from app.models.incident import Incident, IncidentType, IncidentSeverity, IncidentSource, IncidentStatus
from app.models.sos_event import SOSEvent, SOSStatus
from app.models.community_post import CommunityPost, PostStatus
from app.models.comment import Comment
from app.models.risk_score import RiskScore, RiskCategory
from app.models.location import Location
from app.models.safety_report import SafetyReport
from app.models.news_article import NewsArticle
from app.models.police_station import PoliceStation
from app.models.hospital import Hospital
from app.models.audit_log import AuditLog


settings.SECRET_KEY = "test-secret-key-for-testing-purposes-only"
settings.JWT_ALGORITHM = "HS256"
settings.JWT_EXPIRATION_HOURS = 24
settings.KARNATAKA_BOUNDS = "11.5,13.5,74.0,78.5"
settings.GEMINI_API_KEY = "test-key"
settings.DEBUG = False
settings.RATE_LIMIT_MAX = 1000
settings.RATE_LIMIT_WINDOW = 60


@pytest.fixture(scope="session")
def test_engine():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False,
    )

    @event.listens_for(engine.sync_engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
        dbapi_connection.create_function("GeomFromEWKT", -1, lambda *a: a[0] if a else None)
        dbapi_connection.create_function("AsEWKB", 1, lambda x: x)
        dbapi_connection.create_function("ST_MakePoint", 2, lambda x, y: f"POINT({x} {y})")
        dbapi_connection.create_function("ST_SetSRID", 2, lambda g, s: g)
        dbapi_connection.create_function("ST_Distance", 2, lambda a, b: 0.0)
        dbapi_connection.create_function("ST_DWithin", 3, lambda a, b, r: 1)
        dbapi_connection.create_function("ST_AsGeoJSON", 1, lambda g: '{"type":"Point","coordinates":[0,0]}')
        dbapi_connection.create_function("RecoverGeometryColumn", 5, lambda *a: None)
        dbapi_connection.create_function("DiscardGeometryColumn", 1, lambda *a: None)
        dbapi_connection.create_function("CreateSpatialIndex", 2, lambda *a: None)

    yield engine


@pytest_asyncio.fixture
async def db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    connection = await test_engine.connect()
    transaction = await connection.begin()
    session = AsyncSession(bind=connection, expire_on_commit=False)

    await connection.run_sync(Base.metadata.create_all)

    yield session

    await transaction.rollback()
    await connection.close()


@pytest_asyncio.fixture
async def test_app(db_session: AsyncSession) -> FastAPI:
    app.dependency_overrides[get_db] = lambda: db_session
    yield app
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def async_client(test_app: FastAPI) -> AsyncGenerator[httpx.AsyncClient, None]:
    async with httpx.AsyncClient(app=test_app, base_url="http://testserver") as client:
        yield client


@pytest_asyncio.fixture
async def test_user(db_session: AsyncSession) -> User:
    import bcrypt
    user = User(
        id=uuid.uuid4(),
        email="testuser@example.com",
        name="Test User",
        hashed_password=bcrypt.hashpw(b"anypassword", bcrypt.gensalt()).decode("utf-8"),
        role=UserRole.USER,
        is_verified=False,
        is_active=True,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db_session.add(user)
    await db_session.flush()
    return user


@pytest_asyncio.fixture
async def test_admin(db_session: AsyncSession) -> User:
    import bcrypt
    admin = User(
        id=uuid.uuid4(),
        email="admin@example.com",
        name="Admin User",
        hashed_password=bcrypt.hashpw(b"adminpass", bcrypt.gensalt()).decode("utf-8"),
        role=UserRole.ADMIN,
        is_verified=True,
        is_active=True,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db_session.add(admin)
    await db_session.flush()
    return admin


@pytest_asyncio.fixture
async def auth_headers(test_user: User) -> dict:
    token = jwt.encode(
        {"sub": str(test_user.id), "exp": datetime.utcnow() + timedelta(hours=24), "iat": datetime.utcnow()},
        settings.SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def admin_headers(test_admin: User) -> dict:
    token = jwt.encode(
        {"sub": str(test_admin.id), "exp": datetime.utcnow() + timedelta(hours=24), "iat": datetime.utcnow()},
        settings.SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def sample_incident(db_session: AsyncSession, test_user: User) -> Incident:
    incident = Incident(
        id=uuid.uuid4(),
        incident_type=IncidentType.THEFT,
        severity=IncidentSeverity.MEDIUM,
        source=IncidentSource.USER_REPORT,
        status=IncidentStatus.PENDING,
        confidence_score=0.0,
        latitude=12.9716,
        longitude=77.5946,
        geom=None,
        description="Test incident description",
        title="Test Incident",
        district="Bengaluru Urban",
        city="Bengaluru",
        user_id=test_user.id,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db_session.add(incident)
    await db_session.flush()
    return incident


@pytest_asyncio.fixture
async def sample_location(db_session: AsyncSession) -> Location:
    location = Location(
        id=uuid.uuid4(),
        name="Test Location",
        latitude=12.9716,
        longitude=77.5946,
        district="Bengaluru Urban",
        city="Bengaluru",
        created_at=datetime.utcnow(),
    )
    db_session.add(location)
    await db_session.flush()
    return location


@pytest_asyncio.fixture
async def sample_post(db_session: AsyncSession, test_user: User) -> CommunityPost:
    post = CommunityPost(
        id=uuid.uuid4(),
        user_id=test_user.id,
        content="Test community post content",
        post_type="general",
        status=PostStatus.ACTIVE,
        upvotes=0,
        downvotes=0,
        is_verified=False,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db_session.add(post)
    await db_session.flush()
    return post


@pytest_asyncio.fixture
async def sample_comment(db_session: AsyncSession, test_user: User, sample_post: CommunityPost) -> Comment:
    comment = Comment(
        id=uuid.uuid4(),
        post_id=sample_post.id,
        user_id=test_user.id,
        content="Test comment content",
        upvotes=0,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db_session.add(comment)
    await db_session.flush()
    return comment


@pytest_asyncio.fixture
async def sample_sos(db_session: AsyncSession, test_user: User) -> SOSEvent:
    sos = SOSEvent(
        id=uuid.uuid4(),
        user_id=test_user.id,
        latitude=12.9716,
        longitude=77.5946,
        geom=None,
        message="Test SOS message",
        status=SOSStatus.TRIGGERED,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db_session.add(sos)
    await db_session.flush()
    return sos


def pytest_configure(config):
    config.addinivalue_line("markers", "asyncio: mark test as async")
    config.addinivalue_line("markers", "auth: authentication tests")
    config.addinivalue_line("markers", "incident: incident tests")
    config.addinivalue_line("markers", "risk: risk assessment tests")
    config.addinivalue_line("markers", "route: route intelligence tests")
    config.addinivalue_line("markers", "sos: sos tests")
    config.addinivalue_line("markers", "community: community tests")
    config.addinivalue_line("markers", "chat: chat tests")
    config.addinivalue_line("markers", "admin: admin tests")
    config.addinivalue_line("markers", "agents: agent tests")
    config.addinivalue_line("markers", "geo: geo utility tests")
    config.addinivalue_line("markers", "security: security tests")
