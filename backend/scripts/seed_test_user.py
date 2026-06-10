import uuid
import asyncio
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from app.config import settings
from app.models.user import User, UserRole
from app.database import Base

TEST_USER = {
    "email": "alexandra.chen@example.com",
    "name": "Alexandra Chen",
    "phone": "+1-555-023-8471",
    "role": UserRole.USER,
    "is_verified": True,
    "is_active": True,
}


async def seed():
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async_session = async_sessionmaker(engine, expire_on_commit=False)

    async with async_session() as db:
        existing = await db.execute(
            select(User).where(User.email == TEST_USER["email"])
        )
        if existing.scalar_one_or_none():
            print(f"Test user already exists: {TEST_USER['email']}")
            return

        user = User(
            id=uuid.uuid4(),
            email=TEST_USER["email"],
            name=TEST_USER["name"],
            phone=TEST_USER["phone"],
            role=TEST_USER["role"],
            is_verified=TEST_USER["is_verified"],
            is_active=TEST_USER["is_active"],
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.add(user)
        await db.flush()
        await db.commit()
        print("Test user created successfully!")
        print()
        print("Credentials:")
        print(f"  Name:     {TEST_USER['name']}")
        print(f"  Email:    {TEST_USER['email']}")
        print(f"  Password: s3Cure!R0ute#2026")
        print(f"  Phone:    {TEST_USER['phone']}")
        print(f"  Role:     {TEST_USER['role'].value}")
        print()
        print("Login via POST /api/v1/auth/login with email and password.")
        print("(Note: password is for documentation only; the app currently authenticates by email.)")


if __name__ == "__main__":
    asyncio.run(seed())
