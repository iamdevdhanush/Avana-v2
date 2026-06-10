from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from sqlalchemy.exc import IntegrityError, DataError
import logging
import time
import uuid
from datetime import datetime, timezone

from app.config import settings
from app.database import init_db
from app.api.router import api_router
from app.utils.security import sanitize_input, validate_settings

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"Starting {settings.APP_NAME} v{settings.VERSION}")
    try:
        validate_settings()
    except RuntimeError as e:
        logger.critical(f"Configuration validation failed: {e}")
        yield
        return
    try:
        await init_db()
        logger.info("Database initialized")
    except Exception as e:
        logger.warning(f"Database initialization skipped: {e}")
    yield
    logger.info("Shutting down Avana V2")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.VERSION,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_request_id(request: Request, call_next):
    request_id = str(uuid.uuid4())[:8]
    request.state.request_id = request_id
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Process-Time"] = f"{process_time:.4f}s"
    return response


@app.middleware("http")
async def sanitize_inputs(request: Request, call_next):
    if request.method in ("POST", "PUT", "PATCH"):
        original_body = await request.body()
        if original_body:
            try:
                decoded = original_body.decode("utf-8")
                sanitized = sanitize_input(decoded)
                if sanitized != decoded:
                    class SanitizedRequest:
                        def __init__(self, original: Request, body_bytes: bytes):
                            self._original = original
                            self._body = body_bytes

                        async def body(self):
                            return self._body

                        def __getattr__(self, name):
                            return getattr(self._original, name)

                    request = SanitizedRequest(request, sanitized.encode("utf-8"))
            except UnicodeDecodeError:
                pass
    return await call_next(request)


@app.middleware("http")
async def wrap_api_response(request: Request, call_next):
    response = await call_next(request)
    if response.status_code >= 400:
        return response
    content_type = response.headers.get("content-type", "")
    if not content_type.startswith("application/json"):
        return response
    body: bytes = b""
    try:
        body = response.body  # property on Starlette Response
    except Exception:
        try:
            body = response._body  # fallback for newer Starlette internals
        except AttributeError:
            return response
    if not isinstance(body, bytes) or not body:
        return response
    import json
    try:
        data = json.loads(body)
    except (json.JSONDecodeError, TypeError):
        return response
    if isinstance(data, dict) and ("data" in data or "status" in data):
        return response
    wrapped = {"data": data, "status": "success"}
    return JSONResponse(
        content=wrapped,
        status_code=response.status_code,
        headers={k: v for k, v in response.headers.items() if k.lower() not in ("content-length",)},
    )


app.include_router(api_router)


@app.get("/")
async def root():
    return {
        "service": settings.APP_NAME,
        "version": settings.VERSION,
        "status": "running",
        "docs": "/api/docs",
        "api": "/api/v1",
    }


@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "version": settings.VERSION,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    logger.warning(f"Validation error on {request.method} {request.url.path}: {exc.errors()}")
    return JSONResponse(
        status_code=422,
        content={
            "detail": "Validation error",
            "errors": exc.errors(),
            "request_id": getattr(request.state, "request_id", "unknown"),
        },
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail, "request_id": getattr(request.state, "request_id", "unknown")},
    )


@app.exception_handler(IntegrityError)
async def integrity_error_handler(request: Request, exc: IntegrityError):
    logger.error(f"Integrity error on {request.method} {request.url.path}: {exc}")
    detail = "Database constraint violation"
    if "hashed_password" in str(exc):
        detail = "Database schema is outdated. Please run database migrations."
    elif "unique" in str(exc).lower() or "duplicate" in str(exc).lower():
        detail = "Resource already exists"
    return JSONResponse(
        status_code=409,
        content={"detail": detail, "request_id": getattr(request.state, "request_id", "unknown")},
    )


@app.exception_handler(DataError)
async def data_error_handler(request: Request, exc: DataError):
    logger.error(f"Data error on {request.method} {request.url.path}: {exc}")
    return JSONResponse(
        status_code=422,
        content={"detail": "Invalid data format", "request_id": getattr(request.state, "request_id", "unknown")},
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception(f"Unhandled exception on {request.method} {request.url.path}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "request_id": getattr(request.state, "request_id", "unknown")},
    )
