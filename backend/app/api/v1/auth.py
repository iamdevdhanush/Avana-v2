import uuid
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, delete
from sqlalchemy.exc import IntegrityError, DataError
from sqlalchemy.ext.asyncio import AsyncSession

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
from app.utils.security import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token,
    blacklist_token,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Authentication"])


def _build_token_response(user: User) -> AuthResponse:
    access = create_access_token({"sub": str(user.id)})
    refresh = create_refresh_token({"sub": str(user.id)})
    return AuthResponse(
        token=access,
        refresh_token=refresh,
        user=UserResponse(
            id=user.id,
            email=user.email,
            name=user.name,
            role=user.role.value,
            is_verified=user.is_verified,
            created_at=user.created_at,
        ),
    )


@router.post("/signup", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def signup(body: SignupRequest, db: AsyncSession = Depends(get_db)):
    try:
        existing = await db.execute(select(User).where(User.email == body.email))
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Database error checking existing email")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Database error during signup")

    try:
        hashed = hash_password(body.password)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except Exception as e:
        logger.exception("Password hashing failed")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Password processing error")

    user = User(
        id=uuid.uuid4(),
        email=body.email,
        hashed_password=hashed,
        name=body.name,
        role=UserRole.USER,
        is_verified=False,
        is_active=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(user)

    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")
    except DataError:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid data format")
    except Exception:
        await db.rollback()
        logger.exception("Unexpected database error during user creation")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create user")

    try:
        return _build_token_response(user)
    except Exception:
        logger.exception("Token generation failed after user creation")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to generate token")


@router.post("/login", response_model=AuthResponse)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    try:
        result = await db.execute(select(User).where(User.email == body.email))
        user = result.scalar_one_or_none()
    except Exception:
        logger.exception("Database error during login lookup")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Database error during login")

    if not user or not user.hashed_password:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")

    if not verify_password(body.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")

    user.last_login = datetime.now(timezone.utc)
    try:
        await db.flush()
    except Exception:
        await db.rollback()
        logger.exception("Failed to update last_login")

    return _build_token_response(user)


@router.post("/refresh", response_model=AuthResponse)
async def refresh_token(body: dict, db: AsyncSession = Depends(get_db)):
    token = body.get("refresh_token", "")
    payload = decode_token(token)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired refresh token")

    user_id = payload.get("sub")
    try:
        result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
        user = result.scalar_one_or_none()
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User account is inactive")

    return _build_token_response(user)


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
    user.updated_at = datetime.now(timezone.utc)
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


@router.get("/google")
async def google_login():
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Google OAuth is not configured. Use email/password authentication.",
    )


@router.get("/google/callback")
async def google_callback():
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Google OAuth is not configured. Use email/password authentication.",
    )
