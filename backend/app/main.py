import logging
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from sqlalchemy.exc import IntegrityError, DataError

from app.config import settings
from app.database import init_db, check_db
from app.api.router import api_router
from app.utils.security import rate_limit_middleware

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"Starting {settings.APP_NAME} v{settings.VERSION}")
    errs = settings.validate_required()
    if errs:
        for e in errs:
            logger.critical(f"Configuration error: {e}")
        raise RuntimeError(f"Configuration errors: {', '.join(errs)}")
    db_ok = await check_db()
    if not db_ok:
        raise RuntimeError("Database is unreachable. Check DATABASE_URL or POSTGRES_* env vars.")
    await init_db()
    logger.info("Database initialized")
    yield
    logger.info("Shutting down")


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
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=[
        "Authorization",
        "Content-Type",
        "X-Request-ID",
        "X-Process-Time",
    ],
)

app.middleware("http")(rate_limit_middleware)


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


app.include_router(api_router)


@app.get("/")
async def root():
    return {
        "service": settings.APP_NAME,
        "version": settings.VERSION,
        "status": "running",
        "docs": "/api/docs",
        "api": settings.API_PREFIX,
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
        content={
            "detail": exc.detail,
            "request_id": getattr(request.state, "request_id", "unknown"),
        },
    )


@app.exception_handler(IntegrityError)
async def integrity_error_handler(request: Request, exc: IntegrityError):
    logger.error(f"Integrity error on {request.method} {request.url.path}: {exc}")
    detail = "Database constraint violation"
    if "unique" in str(exc).lower() or "duplicate" in str(exc).lower():
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
    detail = str(exc) if settings.DEBUG else "Internal server error"
    return JSONResponse(
        status_code=500,
        content={"detail": detail, "request_id": getattr(request.state, "request_id", "unknown")},
    )


@app.get("/debug/env")
async def debug_env():
    url = settings.build_database_url()
    return {
        "DATABASE_URL_set": bool(settings.DATABASE_URL),
        "resolved_url": f"{url.split('://')[0]}://{url.split('@')[1].split(':')[0]}:***@{url.split('@')[1].split(':')[1].split('/')[0]}" if "@" in url else None,
        "SECRET_KEY_set": bool(settings.SECRET_KEY),
        "DEBUG": settings.DEBUG,
        "CORS_ORIGINS": settings.CORS_ORIGINS,
    }


@app.get("/health/database")
async def health_database():
    from app.database import get_engine
    from sqlalchemy import text
    try:
        engine = get_engine()
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return JSONResponse(
            status_code=503,
            content={"status": "unhealthy", "database": "disconnected", "detail": str(e)},
        )
