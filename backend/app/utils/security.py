import re
import secrets
import logging
import bcrypt
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, List
from fastapi import Request, HTTPException
from jose import jwt, JWTError

from app.config import settings

logger = logging.getLogger(__name__)

_MIN_PASSWORD_LENGTH = 8


def validate_settings():
    """Log warnings on startup if critical settings are missing. Don't block startup."""
    if not settings.SECRET_KEY:
        logger.warning("SECRET_KEY is empty. JWT endpoints will fail until a SECRET_KEY is set.")
    if not settings.DATABASE_URL or "asyncpg" not in settings.DATABASE_URL:
        logger.critical("DATABASE_URL is not properly configured. Database features will be unavailable.")
        raise RuntimeError("DATABASE_URL is not properly configured.")


def hash_password(password: str) -> str:
    if not password or len(password) < _MIN_PASSWORD_LENGTH:
        raise ValueError(f"Password must be at least {_MIN_PASSWORD_LENGTH} characters")
    try:
        return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    except Exception as e:
        logger.exception("bcrypt hashpw failed")
        raise RuntimeError("Password hashing failed") from e


def verify_password(plain: str, hashed: str) -> bool:
    if not hashed:
        return False
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception as e:
        logger.exception("bcrypt checkpw failed")
        return False


def create_access_token(
    data: dict,
    expires_delta: Optional[timedelta] = None,
) -> str:
    if not settings.SECRET_KEY:
        raise RuntimeError("SECRET_KEY is not configured")
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(hours=settings.JWT_EXPIRATION_HOURS)
    )
    to_encode.update({"exp": expire})
    try:
        return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    except JWTError as e:
        logger.exception("JWT encoding failed")
        raise RuntimeError("Token generation failed") from e


def create_rate_limiter():
    ip_requests: Dict[str, List[datetime]] = {}
    max_requests = settings.RATE_LIMIT_MAX
    window_seconds = settings.RATE_LIMIT_WINDOW

    async def rate_limit_middleware(request: Request, call_next):
        client_ip = request.client.host if request.client else "unknown"
        now = datetime.now(timezone.utc)
        if client_ip not in ip_requests:
            ip_requests[client_ip] = []
        ip_requests[client_ip] = [
            t for t in ip_requests[client_ip]
            if (now - t).total_seconds() < window_seconds
        ]
        if len(ip_requests[client_ip]) >= max_requests:
            from fastapi.responses import JSONResponse
            logger.warning(f"Rate limit exceeded for IP: {client_ip}")
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded. Try again later."},
            )
        ip_requests[client_ip].append(now)
        return await call_next(request)

    return rate_limit_middleware


def sanitize_input(text: str) -> str:
    if not text:
        return text
    text = re.sub(r"<script[^>]*>.*?</script>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<[^>]*>", "", text)
    text = re.sub(r"javascript\s*:", "", text, flags=re.IGNORECASE)
    text = re.sub(r"on\w+\s*=\s*[\"'][^\"']*[\"']", "", text, flags=re.IGNORECASE)
    text = re.sub(r"on\w+\s*=\s*\S+", "", text, flags=re.IGNORECASE)
    text = text.replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def generate_secure_key(length: int = 64) -> str:
    return secrets.token_urlsafe(length)
