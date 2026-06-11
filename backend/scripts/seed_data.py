import uuid
import asyncio
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from app.config import settings
from app.database import Base
from app.models.user import User, UserRole
from app.models.police_station import PoliceStation
from app.models.hospital import Hospital, HospitalType
from app.utils.security import hash_password

BANGALORE_POLICE_STATIONS = [
    {"name": "Cubbon Park Police Station", "latitude": 12.9767, "longitude": 77.5920, "district": "Bengaluru Urban", "city": "Bangalore", "phone": "080-22943200", "has_emergency_number": True, "station_type": "police_station"},
    {"name": "Koramangala Police Station", "latitude": 12.9345, "longitude": 77.6145, "district": "Bengaluru Urban", "city": "Bangalore", "phone": "080-25533000", "has_emergency_number": True, "station_type": "police_station"},
    {"name": "Indiranagar Police Station", "latitude": 12.9719, "longitude": 77.6412, "district": "Bengaluru Urban", "city": "Bangalore", "phone": "080-25210841", "has_emergency_number": True, "station_type": "police_station"},
    {"name": "Jayanagar Police Station", "latitude": 12.9308, "longitude": 77.5835, "district": "Bengaluru Urban", "city": "Bangalore", "phone": "080-26632121", "has_emergency_number": True, "station_type": "police_station"},
    {"name": "Malleshwaram Police Station", "latitude": 12.9969, "longitude": 77.5694, "district": "Bengaluru Urban", "city": "Bangalore", "phone": "080-23468111", "has_emergency_number": True, "station_type": "police_station"},
    {"name": "Whitefield Police Station", "latitude": 12.9698, "longitude": 77.7499, "district": "Bengaluru Urban", "city": "Bangalore", "phone": "080-28452111", "has_emergency_number": True, "station_type": "police_station"},
    {"name": "MG Road Police Station", "latitude": 12.9756, "longitude": 77.6066, "district": "Bengaluru Urban", "city": "Bangalore", "phone": "080-25585555", "has_emergency_number": True, "station_type": "police_station"},
    {"name": "Yeshwanthpur Police Station", "latitude": 13.0227, "longitude": 77.5424, "district": "Bengaluru Urban", "city": "Bangalore", "phone": "080-23376111", "has_emergency_number": True, "station_type": "police_station"},
    {"name": "Banashankari Police Station", "latitude": 12.9231, "longitude": 77.5463, "district": "Bengaluru Urban", "city": "Bangalore", "phone": "080-26705555", "has_emergency_number": True, "station_type": "police_station"},
    {"name": "RT Nagar Police Station", "latitude": 13.0197, "longitude": 77.5956, "district": "Bengaluru Urban", "city": "Bangalore", "phone": "080-23332323", "has_emergency_number": True, "station_type": "police_station"},
    {"name": "Mysuru City Police Station", "latitude": 12.2958, "longitude": 76.6394, "district": "Mysuru", "city": "Mysuru", "phone": "0821-2444000", "has_emergency_number": True, "station_type": "police_station"},
    {"name": "Hubli Police Station", "latitude": 15.3500, "longitude": 75.1400, "district": "Dharwad", "city": "Hubli", "phone": "0836-2353800", "has_emergency_number": True, "station_type": "police_station"},
    {"name": "Mangaluru Police Station", "latitude": 12.8698, "longitude": 74.8420, "district": "Dakshina Kannada", "city": "Mangaluru", "phone": "0824-2220500", "has_emergency_number": True, "station_type": "police_station"},
    {"name": "Belagavi Police Station", "latitude": 15.8497, "longitude": 74.4977, "district": "Belagavi", "city": "Belagavi", "phone": "0831-2405201", "has_emergency_number": True, "station_type": "police_station"},
    {"name": "Davangere Police Station", "latitude": 14.4660, "longitude": 75.9240, "district": "Davangere", "city": "Davangere", "phone": "08192-251444", "has_emergency_number": True, "station_type": "police_station"},
]

BANGALORE_HOSPITALS = [
    {"name": "NIMHANS", "latitude": 12.9427, "longitude": 77.5969, "district": "Bengaluru Urban", "city": "Bangalore", "hospital_type": HospitalType.GOVERNMENT, "emergency_services": True, "ambulance_available": True, "trauma_center": True},
    {"name": "Victoria Hospital", "latitude": 12.9618, "longitude": 77.5653, "district": "Bengaluru Urban", "city": "Bangalore", "hospital_type": HospitalType.GOVERNMENT, "emergency_services": True, "ambulance_available": True, "trauma_center": True},
    {"name": "St. John's Medical College Hospital", "latitude": 12.9287, "longitude": 77.6220, "district": "Bengaluru Urban", "city": "Bangalore", "hospital_type": HospitalType.TRUST, "emergency_services": True, "ambulance_available": True, "trauma_center": False},
    {"name": "Manipal Hospital (Old Airport Road)", "latitude": 12.9602, "longitude": 77.6497, "district": "Bengaluru Urban", "city": "Bangalore", "hospital_type": HospitalType.PRIVATE, "emergency_services": True, "ambulance_available": True, "trauma_center": True},
    {"name": "Apollo Hospital (Jayanagar)", "latitude": 12.9260, "longitude": 77.5930, "district": "Bengaluru Urban", "city": "Bangalore", "hospital_type": HospitalType.PRIVATE, "emergency_services": True, "ambulance_available": True, "trauma_center": True},
    {"name": "KIMS Hospital", "latitude": 12.9657, "longitude": 77.5740, "district": "Bengaluru Urban", "city": "Bangalore", "hospital_type": HospitalType.GOVERNMENT, "emergency_services": True, "ambulance_available": True, "trauma_center": True},
    {"name": "MS Ramaiah Memorial Hospital", "latitude": 13.0019, "longitude": 77.5706, "district": "Bengaluru Urban", "city": "Bangalore", "hospital_type": HospitalType.PRIVATE, "emergency_services": True, "ambulance_available": True, "trauma_center": False},
    {"name": "Fortis Hospital (Cunningham Road)", "latitude": 12.9835, "longitude": 77.6015, "district": "Bengaluru Urban", "city": "Bangalore", "hospital_type": HospitalType.PRIVATE, "emergency_services": True, "ambulance_available": True, "trauma_center": True},
    {"name": "Krishna Rajendra Hospital (Mysuru)", "latitude": 12.3200, "longitude": 76.6200, "district": "Mysuru", "city": "Mysuru", "hospital_type": HospitalType.GOVERNMENT, "emergency_services": True, "ambulance_available": True, "trauma_center": True},
    {"name": "Wenlock Hospital (Mangaluru)", "latitude": 12.8680, "longitude": 74.8400, "district": "Dakshina Kannada", "city": "Mangaluru", "hospital_type": HospitalType.GOVERNMENT, "emergency_services": True, "ambulance_available": True, "trauma_center": True},
]

ADMIN_USER = {
    "email": "admin@avana-safety.app",
    "password": "Admin@2026!Secure",
    "name": "Avana Admin",
    "role": UserRole.ADMIN,
    "is_verified": True,
    "is_active": True,
}

TEST_USER = {
    "email": "alexandra.chen@example.com",
    "password": "s3Cure!R0ute#2026",
    "name": "Alexandra Chen",
    "role": UserRole.USER,
    "is_verified": True,
    "is_active": True,
}


async def seed():
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        from sqlalchemy import text
        await conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS reputation INTEGER DEFAULT 0"))
        await conn.run_sync(Base.metadata.create_all)

    async_session = async_sessionmaker(engine, expire_on_commit=False)

    async with async_session() as db:
        existing_admin = await db.execute(
            select(User).where(User.email == ADMIN_USER["email"])
        )
        if existing_admin.scalar_one_or_none():
            print(f"Admin user already exists: {ADMIN_USER['email']}")
        else:
            user = User(
                id=uuid.uuid4(),
                email=ADMIN_USER["email"],
                hashed_password=hash_password(ADMIN_USER["password"]),
                name=ADMIN_USER["name"],
                role=ADMIN_USER["role"],
                is_verified=ADMIN_USER["is_verified"],
                is_active=ADMIN_USER["is_active"],
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            db.add(user)
            print(f"Admin user created: {ADMIN_USER['email']}")
            print(f"  Password: {ADMIN_USER['password']}")

        existing_test = await db.execute(
            select(User).where(User.email == TEST_USER["email"])
        )
        if existing_test.scalar_one_or_none():
            print(f"Test user already exists: {TEST_USER['email']}")
        else:
            test_user = User(
                id=uuid.uuid4(),
                email=TEST_USER["email"],
                hashed_password=hash_password(TEST_USER["password"]),
                name=TEST_USER["name"],
                role=TEST_USER["role"],
                is_verified=TEST_USER["is_verified"],
                is_active=TEST_USER["is_active"],
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            db.add(test_user)
            print(f"Test user created: {TEST_USER['email']}")
            print(f"  Password: {TEST_USER['password']}")

        await db.commit()

    async with async_session() as db:
        for ps in BANGALORE_POLICE_STATIONS:
            existing = await db.execute(
                select(PoliceStation).where(
                    PoliceStation.name == ps["name"],
                    PoliceStation.latitude == ps["latitude"],
                )
            )
            if existing.scalar_one_or_none():
                print(f"  Police station exists: {ps['name']}")
                continue
            station = PoliceStation(
                id=uuid.uuid4(),
                name=ps["name"],
                latitude=ps["latitude"],
                longitude=ps["longitude"],
                district=ps["district"],
                city=ps["city"],
                phone=ps.get("phone"),
                has_emergency_number=ps.get("has_emergency_number", False),
                station_type=ps.get("station_type", "police_station"),
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            db.add(station)
            print(f"  Police station added: {ps['name']}")
        await db.commit()

    async with async_session() as db:
        for h in BANGALORE_HOSPITALS:
            existing = await db.execute(
                select(Hospital).where(
                    Hospital.name == h["name"],
                    Hospital.latitude == h["latitude"],
                )
            )
            if existing.scalar_one_or_none():
                print(f"  Hospital exists: {h['name']}")
                continue
            hospital = Hospital(
                id=uuid.uuid4(),
                name=h["name"],
                latitude=h["latitude"],
                longitude=h["longitude"],
                district=h["district"],
                city=h["city"],
                hospital_type=h["hospital_type"],
                emergency_services=h.get("emergency_services", False),
                ambulance_available=h.get("ambulance_available", False),
                trauma_center=h.get("trauma_center", False),
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            db.add(hospital)
            print(f"  Hospital added: {h['name']}")
        await db.commit()

    print("\nSeed complete!")


if __name__ == "__main__":
    from sqlalchemy import select
    asyncio.run(seed())
