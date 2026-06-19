import asyncio
import logging
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from sqlalchemy.exc import IntegrityError, DataError

from app.config import settings
from app.database import init_db, check_db, validate_schema
from app.api.router import api_router
from app.dependencies import require_admin
from app.models.user import User
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

    await validate_schema()
    logger.info("Schema validation complete")

    # Gemini startup diagnostic
    try:
        from app.services.gemini import gemini_service as gs
        import google.generativeai as genai
        sd = gs.get_status()
        logger.info(
            f"[GEMINI_DIAG] enabled={bool(settings.GEMINI_API_KEY)} "
            f"key_present={bool(settings.GEMINI_API_KEY and len(settings.GEMINI_API_KEY) >= 10)} "
            f"sdk=google-generativeai-{genai.__version__} "
            f"auth_method=api_key (genai.configure) "
            f"status={sd.get('status', 'unknown')}"
        )
    except Exception as diag_err:
        logger.warning(f"[GEMINI_DIAG] diagnostic failed: {diag_err}")

    await _run_alembic_migrations()
    await _ensure_risk_scores_constraint()
    asyncio.create_task(_bootstrap_heatmap_data())

    yield
    logger.info("Shutting down")


async def _run_alembic_migrations():
    import os
    import sys
    backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    logger.info("[MIGRATE] Running pending database migrations...")
    try:
        proc = await asyncio.create_subprocess_exec(
            sys.executable, "-m", "alembic", "upgrade", "head",
            cwd=backend_dir,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode == 0:
            logger.info(f"[MIGRATE] Migrations applied successfully")
        else:
            logger.warning(f"[MIGRATE] Alembic exit code {proc.returncode}: {stderr.decode().strip()}")
    except Exception as e:
        logger.warning(f"[MIGRATE] Failed to run migrations: {e}")


async def _ensure_risk_scores_constraint():
    from sqlalchemy import text
    from app.database import get_engine
    try:
        engine = get_engine()
        async with engine.connect() as conn:
            table_exists = await conn.execute(text("""
                SELECT 1 FROM information_schema.tables
                WHERE table_schema = 'public' AND table_name = 'risk_scores'
            """))
            if table_exists.fetchone() is None:
                logger.info("[SCHEMA] risk_scores table does not exist yet — skipping constraint check")
                return
        async with engine.begin() as conn:
            result = await conn.execute(text("""
                SELECT 1 FROM pg_constraint
                WHERE conname = 'uq_risk_scores_lat_lng'
                  AND conrelid = 'risk_scores'::regclass
            """))
            if result.fetchone() is None:
                logger.info("[SCHEMA] Missing uq_risk_scores_lat_lng — creating now")
                await conn.execute(text("""
                    DELETE FROM risk_scores
                    WHERE id NOT IN (
                        SELECT DISTINCT ON (latitude, longitude) id
                        FROM risk_scores
                        ORDER BY latitude, longitude, calculated_at DESC NULLS LAST
                    )
                """))
                await conn.execute(text("""
                    ALTER TABLE risk_scores
                    ADD CONSTRAINT uq_risk_scores_lat_lng
                    UNIQUE (latitude, longitude)
                """))
                logger.info("[SCHEMA] Created unique constraint uq_risk_scores_lat_lng")
            else:
                logger.info("[SCHEMA] Constraint uq_risk_scores_lat_lng already exists")
    except Exception as e:
        logger.error(f"[SCHEMA] Failed to ensure constraint: {e}")


async def _bootstrap_heatmap_data():
    from sqlalchemy import text
    from app.database import get_session_factory

    try:
        factory = get_session_factory()
        async with factory() as session:
            fresh_count = await session.scalar(
                text("SELECT COUNT(*) FROM risk_scores WHERE calculated_at >= NOW() - INTERVAL '48 hours'")
            )
            if fresh_count and fresh_count > 0:
                logger.info(f"[BOOTSTRAP] risk_scores has {fresh_count} fresh rows — skipping seed")
                return
            all_count = await session.scalar(text("SELECT COUNT(*) FROM risk_scores"))
            if all_count and all_count > 0:
                logger.info(f"[BOOTSTRAP] risk_scores has {all_count} stale rows — reseeding anyway")
                await session.execute(text("DELETE FROM risk_scores"))

        logger.info("[BOOTSTRAP] risk_scores is empty — running initial pipeline")
        from app.pipeline.intelligence import run_intelligence_pipeline

        result = await run_intelligence_pipeline()

        if result.get("status") == "skipped" and "gemini" in result.get("reason", ""):
            logger.info("[BOOTSTRAP] Pipeline skipped (Gemini unavailable) — retrying with mock mode")
            original = settings.MOCK_INTELLIGENCE_MODE
            settings.MOCK_INTELLIGENCE_MODE = True
            try:
                result = await run_intelligence_pipeline()
                logger.info(f"[BOOTSTRAP] Mock pipeline result: {result.get('status', 'unknown')}")
            finally:
                settings.MOCK_INTELLIGENCE_MODE = original

        heat_count = result.get("steps", {}).get("heatmap", {}).get("points_generated", 0)
        if heat_count > 0:
            logger.info(f"[BOOTSTRAP] Pipeline complete — {heat_count} heatmap points generated")
            return

        logger.warning("[BOOTSTRAP] Pipeline produced no heatmap points — falling back to direct seed")
    except Exception as e:
        logger.error(f"[BOOTSTRAP] Pipeline failed: {e} — falling back to direct seed")

    logger.info("[BOOTSTRAP] Seeding risk_scores directly with Karnataka city data")
    from app.pipeline.risk import ensure_default_location
    loc_id = await ensure_default_location()
    cities = [
        (12.9716, 77.5946, 65.0, "HIGH_RISK"),
        (12.2958, 76.6394, 45.0, "MODERATE"),
        (12.9141, 74.8560, 30.0, "MODERATE"),
        (15.3647, 75.1240, 55.0, "HIGH_RISK"),
        (17.3290, 76.8344, 40.0, "MODERATE"),
        (14.4419, 75.9172, 35.0, "MODERATE"),
        (15.8573, 74.5069, 20.0, "SAFE"),
        (15.8497, 74.4977, 25.0, "SAFE"),
        (13.3409, 74.7421, 15.0, "SAFE"),
        (13.9299, 75.5681, 35.0, "MODERATE"),   # Shivamogga
    ]
    factory = get_session_factory()
    async with factory() as session:
        for lat, lng, score, category in cities:
            try:
                await session.execute(
                    text("""
                        INSERT INTO risk_scores
                            (id, location_id, latitude, longitude, score, category,
                             metadata, calculated_at, created_at)
                        VALUES (
                            gen_random_uuid(),
                            :location_id, :lat, :lng, :score, :cat,
                            '{}'::jsonb, NOW(), NOW()
                        )
                    """),
                    {"lat": lat, "lng": lng, "score": score, "cat": category, "location_id": loc_id},
                )
            except Exception as e:
                logger.warning(f"[BOOTSTRAP] Failed to insert ({lat}, {lng}): {e}")
                try:
                    await session.rollback()
                except Exception:
                    pass
        try:
            await session.commit()
        except Exception as e:
            logger.error(f"[BOOTSTRAP] Commit failed: {e}")
    logger.info(f"[BOOTSTRAP] Seeded {len(cities)} direct risk_score entries")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.VERSION,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=settings.CORS_ORIGINS_REGEX,
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
async def debug_env(admin: User = Depends(require_admin)):
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


@app.get("/health/gemini")
async def health_gemini():
    from app.services.gemini import gemini_service, GeminiQuotaExceeded
    status = gemini_service.get_status()
    if status.get("status") == "QUOTA_EXCEEDED":
        return {
            "status": "unavailable",
            "detail": "Gemini API quota exceeded",
            "note": "Women-safety classification uses keyword fallback",
        }
    if status.get("status") == "OFFLINE":
        return {
            "status": "unavailable",
            "detail": status.get("error", "Gemini API not configured or unreachable"),
            "note": "Women-safety classification uses keyword fallback",
        }
    import asyncio
    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            lambda: gemini_service.generate("Respond with only the word: OK"),
        )
        if result and "OK" in result:
            return {"status": "available", "model": "gemini-2.0-flash"}
        return {
            "status": "unavailable",
            "detail": "Gemini test request returned unexpected response",
            "note": "Women-safety classification uses keyword fallback",
        }
    except GeminiQuotaExceeded:
        return {
            "status": "unavailable",
            "detail": "Gemini API quota exceeded",
            "note": "Women-safety classification uses keyword fallback",
        }
    except Exception as e:
        logger.error(f"Gemini health check failed: {e}")
        return {
            "status": "unavailable",
            "detail": "Gemini API not configured or unreachable",
            "note": "Women-safety classification uses keyword fallback",
        }


@app.get("/api/v1/debug/gemini")
async def debug_gemini(admin: User = Depends(require_admin)):
    from app.services.gemini import gemini_service, GeminiQuotaExceeded, GeminiAuthError
    import google.generativeai as genai

    result = {
        "status": "failure",
        "diagnostics": {
            "GEMINI_API_KEY_configured": bool(settings.GEMINI_API_KEY),
            "GEMINI_API_KEY_length": len(settings.GEMINI_API_KEY) if settings.GEMINI_API_KEY else 0,
            "GEMINI_API_KEY_prefix": (settings.GEMINI_API_KEY[:6] + "...") if settings.GEMINI_API_KEY and len(settings.GEMINI_API_KEY) >= 6 else "N/A",
            "sdk": f"google-generativeai-{genai.__version__}",
            "auth_method": "api_key (genai.configure)",
            "service_status": gemini_service.get_status(),
        },
    }

    if not settings.GEMINI_API_KEY:
        result["error"] = "GEMINI_API_KEY not configured"
        return JSONResponse(status_code=503, content=result)

    if len(settings.GEMINI_API_KEY) < 10:
        result["error"] = "GEMINI_API_KEY too short (< 10 chars)"
        return JSONResponse(status_code=503, content=result)

    import asyncio
    loop = asyncio.get_event_loop()
    try:
        resp = await loop.run_in_executor(
            None,
            lambda: gemini_service.generate("Reply with OK"),
        )
        if resp and "OK" in resp:
            result["status"] = "success"
            result["response"] = resp
            return result
        result["error"] = f"Unexpected response: {resp}"
        return JSONResponse(status_code=502, content=result)
    except GeminiQuotaExceeded as e:
        result["error"] = f"QUOTA_EXCEEDED: {e}"
        return JSONResponse(status_code=429, content=result)
    except GeminiAuthError as e:
        result["error"] = f"AUTH_FAILED: {e}"
        result["diagnostics"]["auth_error_detail"] = str(e)
        return JSONResponse(status_code=401, content=result)
    except Exception as e:
        err_str = str(e)
        if "ACCESS_TOKEN_TYPE_UNSUPPORTED" in err_str:
            result["error"] = (
                "AUTH_FAILED: ACCESS_TOKEN_TYPE_UNSUPPORTED — Gemini API received an OAuth token "
                "instead of an API key. This means genai.configure(api_key=...) did not apply. "
                "Check that GEMINI_API_KEY env var is set correctly in Render dashboard "
                "(no quotes, no whitespace)."
            )
            result["diagnostics"]["auth_error_detail"] = err_str
            return JSONResponse(status_code=401, content=result)
        result["error"] = str(e)
        return JSONResponse(status_code=503, content=result)
