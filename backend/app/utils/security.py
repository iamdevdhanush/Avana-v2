import re
import secrets
import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, List, Tuple
from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse
from jose import jwt, JWTError
import bcrypt

from app.config import settings

logger = logging.getLogger(__name__)

_MIN_PASSWORD_LENGTH = 8
_blacklisted_tokens: set = set()


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


def create_access_token(data: dict) -> str:
    if not settings.SECRET_KEY:
        raise RuntimeError("SECRET_KEY is not configured")
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_refresh_token(data: dict) -> str:
    if not settings.SECRET_KEY:
        raise RuntimeError("SECRET_KEY is not configured")
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh"})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> Optional[dict]:
    if token in _blacklisted_tokens:
        return None
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        return payload
    except JWTError:
        return None


def blacklist_token(token: str):
    _blacklisted_tokens.add(token)


def generate_secure_key(length: int = 64) -> str:
    return secrets.token_urlsafe(length)


# ---- Rate Limiter ----

class InMemoryRateLimiter:
    def __init__(self):
        self._windows: Dict[str, List[float]] = {}

    def check(self, key: str, max_requests: int = None, window_seconds: int = None) -> Tuple[bool, int]:
        max_r = max_requests or settings.RATE_LIMIT_MAX
        window_s = window_seconds or settings.RATE_LIMIT_WINDOW
        now = time.time()
        if key not in self._windows:
            self._windows[key] = []
        self._windows[key] = [t for t in self._windows[key] if now - t < window_s]
        if len(self._windows[key]) >= max_r:
            return False, int(window_s - (now - self._windows[key][0]))
        self._windows[key].append(now)
        return True, 0


rate_limiter = InMemoryRateLimiter()


async def rate_limit_middleware(request: Request, call_next):
    client_ip = request.client.host if request.client else "unknown"
    path = request.url.path
    key = f"{client_ip}:{path}"

    if path.startswith("/api/v1/auth"):
        max_req = 20
        window_s = 60
    elif path.startswith("/api/v1/admin"):
        max_req = 60
        window_s = 60
    else:
        max_req = settings.RATE_LIMIT_MAX
        window_s = settings.RATE_LIMIT_WINDOW

    allowed, retry_after = rate_limiter.check(key, max_req, window_s)
    if not allowed:
        logger.warning(f"Rate limit exceeded for {key}")
        return JSONResponse(
            status_code=429,
            content={"detail": "Rate limit exceeded. Try again later."},
            headers={"Retry-After": str(retry_after)},
        )
    return await call_next(request)


# ---- Input Sanitization ----

_SANITIZE_PATTERNS = [
    (re.compile(r"<script[^>]*>.*?</script>", re.DOTALL | re.IGNORECASE), ""),
    (re.compile(r"javascript\s*:", re.IGNORECASE), ""),
    (re.compile(r"on\w+\s*=\s*[\"'][^\"']*[\"']", re.IGNORECASE), ""),
    (re.compile(r"on\w+\s*=\s*\S+", re.IGNORECASE), ""),
    (re.compile(r"<[^>]*>"), ""),
]


def sanitize_input(text: str) -> str:
    if not text:
        return text
    for pattern, replacement in _SANITIZE_PATTERNS:
        text = pattern.sub(replacement, text)
    text = text.replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&")
    text = re.sub(r"\s+", " ", text).strip()
    return text


# ---- Security Headers Middleware ----

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "X-XSS-Protection": "1; mode=block",
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "geolocation=(self), camera=(), microphone=()",
    "Cross-Origin-Embedder-Policy": "require-corp",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Cross-Origin-Resource-Policy": "same-origin",
}


async def add_security_headers(request, call_next):
    response = await call_next(request)
    for header, value in SECURITY_HEADERS.items():
        response.headers[header] = value
    return response
