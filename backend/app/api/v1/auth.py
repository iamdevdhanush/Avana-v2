import uuid
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from jose import jwt
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from passlib.context import CryptContext

from app.config import settings
from app.database import get_db
from app.dependencies import get_current_user, require_user
from app.models.user import User, EmergencyContact, UserRole
from app.schemas.auth import (
    LoginRequest,
    SignupRequest,
    AuthResponse,
    UserResponse,
    UserUpdateRequest,
    EmergencyContactCreate,
    EmergencyContactResponse,
)

router = APIRouter(prefix="/auth", tags=["Authentication"])

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def _create_token(user_id: str) -> str:
    expire = datetime.utcnow() + timedelta(hours=settings.JWT_EXPIRATION_HOURS)
    payload = {"sub": user_id, "exp": expire, "iat": datetime.utcnow()}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


@router.post("/signup", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def signup(body: SignupRequest, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(select(User).where(User.email == body.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    user = User(
        id=uuid.uuid4(),
        email=body.email,
        name=body.name,
        role=UserRole.USER,
        is_verified=False,
        is_active=True,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(user)
    await db.flush()

    token = _create_token(str(user.id))
    return AuthResponse(
        access_token=token,
        token_type="bearer",
        user=UserResponse(
            id=user.id,
            email=user.email,
            name=user.name,
            role=user.role.value,
            is_verified=user.is_verified,
            created_at=user.created_at,
        ),
    )


@router.post("/login", response_model=AuthResponse)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")

    user.last_login = datetime.utcnow()
    await db.flush()

    token = _create_token(str(user.id))
    return AuthResponse(
        access_token=token,
        token_type="bearer",
        user=UserResponse(
            id=user.id,
            email=user.email,
            name=user.name,
            role=user.role.value,
            is_verified=user.is_verified,
            created_at=user.created_at,
        ),
    )


@router.post("/logout", status_code=status.HTTP_200_OK)
async def logout(user: User = Depends(require_user)):
    return {"message": "Logged out successfully"}


@router.get("/me", response_model=UserResponse)
async def get_me(user: User = Depends(require_user)):
    return UserResponse(
        id=user.id,
        email=user.email,
        name=user.name,
        role=user.role.value,
        is_verified=user.is_verified,
        created_at=user.created_at,
    )


@router.put("/me", response_model=UserResponse)
async def update_me(
    body: UserUpdateRequest,
    user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    if body.name is not None:
        user.name = body.name
    if body.phone is not None:
        user.phone = body.phone
    user.updated_at = datetime.utcnow()
    await db.flush()
    return UserResponse(
        id=user.id,
        email=user.email,
        name=user.name,
        role=user.role.value,
        is_verified=user.is_verified,
        created_at=user.created_at,
    )


@router.get("/emergency-contacts", response_model=list[EmergencyContactResponse])
async def list_contacts(
    user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(EmergencyContact).where(EmergencyContact.user_id == user.id)
    )
    contacts = result.scalars().all()
    return [
        EmergencyContactResponse(
            id=c.id,
            name=c.name,
            phone=c.phone,
            relationship=c.relationship,
            is_primary=c.is_primary,
        )
        for c in contacts
    ]


@router.post("/emergency-contacts", response_model=EmergencyContactResponse, status_code=status.HTTP_201_CREATED)
async def add_contact(
    body: EmergencyContactCreate,
    user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    contact = EmergencyContact(
        id=uuid.uuid4(),
        user_id=user.id,
        name=body.name,
        phone=body.phone,
        relationship=body.relationship,
        is_primary=body.is_primary,
    )
    db.add(contact)
    await db.flush()
    return EmergencyContactResponse(
        id=contact.id,
        name=contact.name,
        phone=contact.phone,
        relationship=contact.relationship,
        is_primary=contact.is_primary,
    )


@router.delete("/emergency-contacts/{id}", status_code=status.HTTP_200_OK)
async def delete_contact(
    id: uuid.UUID,
    user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(EmergencyContact).where(
            EmergencyContact.id == id, EmergencyContact.user_id == user.id
        )
    )
    contact = result.scalar_one_or_none()
    if not contact:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contact not found")
    await db.delete(contact)
    await db.flush()
    return {"message": "Contact deleted successfully"}
