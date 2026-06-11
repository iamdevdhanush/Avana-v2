import uuid
from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.config import settings
from app.database import get_db
from app.models.user import User
from app.utils.security import decode_token

security_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
    db: AsyncSession = Depends(get_db),
) -> Optional[User]:
    if not credentials:
        return None
    payload = decode_token(credentials.credentials)
    if not payload:
        return None
    if payload.get("type") != "access":
        return None
    user_id = payload.get("sub")
    if not user_id:
        return None
    try:
        result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
        return result.scalar_one_or_none()
    except (ValueError, Exception):
        return None


async def require_user(user: Optional[User] = Depends(get_current_user)) -> User:
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


async def require_admin(user: User = Depends(require_user)) -> User:
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return user
