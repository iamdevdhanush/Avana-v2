import uuid
import logging
from datetime import datetime, timedelta, timezone

import bcrypt
from fastapi import APIRouter, Depends, HTTPException, status
from jose import jwt, JWTError
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

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Authentication"])


def _create_token(user_id: str) -> str:
    if not settings.SECRET_KEY:
        logger.critical("SECRET_KEY is not configured")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Server configuration error: JWT secret is not set",
        )
    expire = datetime.now(timezone.utc) + timedelta(hours=settings.JWT_EXPIRATION_HOURS)
    payload = {"sub": user_id, "exp": expire, "iat": datetime.now(timezone.utc)}
    try:
        return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    except JWTError as e:
        logger.exception("JWT encoding failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate authentication token",
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
        hashed = bcrypt.hashpw(body.password.encode("utf-8"), bcrypt.gensalt())
    except Exception as e:
        logger.exception("Password hashing failed")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Password processing error")

    user = User(
        id=uuid.uuid4(),
        email=body.email,
        hashed_password=hashed.decode("utf-8"),
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
    except IntegrityError as e:
        await db.rollback()
        if "hashed_password" in str(e):
            logger.critical("hashed_password column missing from users table; run alembic migration")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Database schema is outdated. Please run database migrations.",
            )
        if "unique" in str(e).lower() or "duplicate" in str(e).lower():
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")
        logger.exception("Integrity error during user creation")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid user data")
    except DataError as e:
        await db.rollback()
        logger.exception("Data error during user creation")
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid data format")
    except Exception as e:
        await db.rollback()
        logger.exception("Unexpected database error during user creation")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create user")

    try:
        token = _create_token(str(user.id))
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Token generation failed after user creation")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to generate token")

    return AuthResponse(
        token=token,
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
    try:
        result = await db.execute(select(User).where(User.email == body.email))
        user = result.scalar_one_or_none()
    except Exception as e:
        logger.exception("Database error during login lookup")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Database error during login")

    if not user or not user.hashed_password:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")

    try:
        if not bcrypt.checkpw(body.password.encode("utf-8"), user.hashed_password.encode("utf-8")):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Password verification failed")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Password verification error")

    user.last_login = datetime.now(timezone.utc)
    try:
        await db.flush()
    except Exception as e:
        await db.rollback()
        logger.exception("Failed to update last_login")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update user")

    token = _create_token(str(user.id))
    return AuthResponse(
        token=token,
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
    if not settings.GOOGLE_CLIENT_ID:
        raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Google OAuth not configured")
    redirect_uri = settings.GOOGLE_REDIRECT_URI
    google_auth_url = (
        "https://accounts.google.com/o/oauth2/v2/auth"
        f"?client_id={settings.GOOGLE_CLIENT_ID}"
        f"&redirect_uri={redirect_uri}"
        "&response_type=code"
        "&scope=openid%20email%20profile"
    )
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url=google_auth_url)


@router.get("/google/callback")
async def google_callback(
    code: str,
    db: AsyncSession = Depends(get_db),
):
    if not settings.GOOGLE_CLIENT_ID or not settings.GOOGLE_CLIENT_SECRET:
        raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Google OAuth not configured")

    import httpx
    token_url = "https://oauth2.googleapis.com/token"
    token_data = {
        "code": code,
        "client_id": settings.GOOGLE_CLIENT_ID,
        "client_secret": settings.GOOGLE_CLIENT_SECRET,
        "redirect_uri": settings.GOOGLE_REDIRECT_URI,
        "grant_type": "authorization_code",
    }
    async with httpx.AsyncClient() as client:
        token_resp = await client.post(token_url, data=token_data)
        if token_resp.status_code != 200:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Failed to exchange Google auth code")
        token_json = token_resp.json()
        access_token = token_json.get("access_token")

        userinfo_resp = await client.get(
            "https://www.googleapis.com/oauth2/v2/userinfo",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if userinfo_resp.status_code != 200:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Failed to get Google user info")
        google_user = userinfo_resp.json()

    email = google_user.get("email")
    name = google_user.get("name", "")
    google_id = google_user.get("id")

    if not email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Google account has no email")

    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if not user:
        user = User(
            id=uuid.uuid4(),
            email=email,
            hashed_password="",
            name=name,
            role=UserRole.USER,
            is_verified=True,
            is_active=True,
            avatar_url=google_user.get("picture"),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db.add(user)
        await db.flush()
    else:
        if google_user.get("picture"):
            user.avatar_url = google_user.get("picture")
        user.updated_at = datetime.now(timezone.utc)
        await db.flush()

    token = _create_token(str(user.id))
    return AuthResponse(
        token=token,
        user=UserResponse(
            id=user.id,
            email=user.email,
            name=user.name,
            role=user.role.value,
            is_verified=user.is_verified,
            created_at=user.created_at,
        ),
    )
