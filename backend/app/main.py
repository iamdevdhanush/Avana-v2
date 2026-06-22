import asyncio
import logging
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from sqlalchemy.exc import IntegrityError, DataError

from app.config import settings
from app.database import init_db, check_db, validate_schema
from app.api.router import api_router
from app.dependencies import require_admin
from app.models.user import User
from app.utils.security import rate_limit_middleware, add_security_headers

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

    await _run_alembic_migrations()
    await _ensure_risk_scores_constraint()
    asyncio.create_task(_bootstrap_offline_data())
    asyncio.create_task(_gemini_diagnostics())

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


async def _gemini_diagnostics():
    """Diagnose Gemini status for logging/health only. Never required for data."""
    try:
        from app.services.gemini import gemini_service as gs
        import google.generativeai as genai
        sd = gs.get_status()
        init_err = getattr(gs, '_init_error', None)
        logger.info(
            f"[GEMINI_DIAG] enabled={bool(settings.GEMINI_API_KEY)} "
            f"key_present={bool(settings.GEMINI_API_KEY and len(settings.GEMINI_API_KEY) >= 10)} "
            f"key_length={len(settings.GEMINI_API_KEY) if settings.GEMINI_API_KEY else 0} "
            f"sdk=google-generativeai-{genai.__version__} "
            f"status={sd.get('status', 'unknown')} "
            f"init_error={init_err}"
        )
        if sd.get("status") != "ONLINE":
            logger.warning(f"[GEMINI_DIAG] Gemini NOT available: status={sd.get('status')} error={sd.get('error')} init_error={init_err}")
    except Exception as diag_err:
        logger.warning(f"[GEMINI_DIAG] diagnostic failed: {diag_err}")


async def _bootstrap_offline_data():
    """
    Offline-first bootstrap. Never depends on Gemini.
    Seeds from CSV if database is empty, generates risk_scores and heatmap.
    """
    from sqlalchemy import text
    from app.database import get_session_factory
    import os

    _file_dir = os.path.dirname(os.path.abspath(__file__))
    _project_root = os.path.dirname(_file_dir)
    SEED_DIR = os.path.join(_project_root, "seed_data")

    try:
        factory = get_session_factory()
        async with factory() as session:
            risk_count = await session.scalar(text("SELECT COUNT(*) FROM risk_scores"))
            incident_count = await session.scalar(text("SELECT COUNT(*) FROM incidents"))

        logger.info(f"[BOOTSTRAP] DB state: {incident_count} incidents, {risk_count} risk_scores")

        # Phase 1: Seed police stations + hospitals if empty
        async with factory() as session:
            ps_count = await session.scalar(text("SELECT COUNT(*) FROM police_stations"))
        if ps_count == 0:
            logger.info("[BOOTSTRAP] police_stations empty — seeding from CSV")
            from scripts.seed_police_hospitals import seed_police_stations, seed_hospitals
            await seed_police_stations(os.path.join(SEED_DIR, "police_stations.csv"))
            await seed_hospitals(os.path.join(SEED_DIR, "hospitals.csv"))
        else:
            logger.info(f"[BOOTSTRAP] police_stations: {ps_count} rows — skipping")

        # Phase 2: Seed incidents if empty
        if incident_count == 0:
            logger.info("[BOOTSTRAP] incidents empty — seeding from CSV")
            from scripts.seed_incidents import seed_incidents
            result = await seed_incidents(os.path.join(SEED_DIR, "incidents.csv"))
            logger.info(f"[BOOTSTRAP] Incident seed result: {result}")
            incident_count = result.get("inserted", 0)

        if incident_count == 0:
            logger.warning("[BOOTSTRAP] No incidents seeded — nothing to bootstrap")
            return

        # Phase 3: Generate risk_scores from seeded incidents
        if risk_count == 0:
            logger.info("[BOOTSTRAP] risk_scores empty — generating from incidents")
            from scripts.seed_risk_scores import seed_risk_scores
            risk_result = await seed_risk_scores()
            logger.info(f"[BOOTSTRAP] Risk score result: {risk_result}")

        # Phase 4: Generate heatmap grid
        async with factory() as session:
            fresh = await session.scalar(
                text("SELECT COUNT(*) FROM risk_scores WHERE calculated_at >= NOW() - INTERVAL '48 hours'")
            )
        if fresh == 0:
            logger.info("[BOOTSTRAP] Generating heatmap grid from seeded data")
            from app.pipeline.heatmap import generate_heatmap_for_bounds
            bounds = [float(x) for x in settings.KARNATAKA_BOUNDS.split(",")]
            sw_lat, sw_lng, ne_lat, ne_lng = bounds[0], bounds[2], bounds[1], bounds[3]
            grid_result = await generate_heatmap_for_bounds(sw_lat, sw_lng, ne_lat, ne_lng, zoom="state")
            logger.info(f"[BOOTSTRAP] Heatmap generated {grid_result.get('points_generated', 0)} points")
        else:
            logger.info(f"[BOOTSTRAP] risk_scores has {fresh} fresh rows — skipping heatmap generation")

    except Exception as e:
        logger.error(f"[BOOTSTRAP] Failed: {e}", exc_info=True)


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

app.add_middleware(GZipMiddleware, minimum_size=1000)

app.middleware("http")(add_security_headers)
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


@app.get("/health/deep")
async def health_deep():
    from app.database import get_engine, get_session_factory
    from sqlalchemy import text
    checks = {}
    overall = "healthy"
    try:
        engine = get_engine()
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        checks["database"] = "connected"
    except Exception as e:
        checks["database"] = f"disconnected: {e}"
        overall = "unhealthy"
    from app.services.gemini import gemini_service
    gs = gemini_service.get_status()
    checks["gemini"] = gs.get("status", "unknown")
    checks["gemini_optional"] = True
    from app.config import settings
    checks["mock_mode"] = settings.MOCK_INTELLIGENCE_MODE
    async with get_session_factory()() as session:
        try:
            incident_count = await session.scalar(text("SELECT COUNT(*) FROM incidents"))
            checks["incidents"] = incident_count or 0
        except Exception:
            checks["incidents"] = -1
        try:
            risk_count = await session.scalar(text("SELECT COUNT(*) FROM risk_scores"))
            checks["risk_scores"] = risk_count or 0
        except Exception:
            checks["risk_scores"] = -1
        try:
            fresh_risk = await session.scalar(text("SELECT COUNT(*) FROM risk_scores WHERE calculated_at >= NOW() - INTERVAL '48 hours'"))
            checks["risk_scores_fresh_48h"] = fresh_risk or 0
        except Exception:
            checks["risk_scores_fresh_48h"] = -1
        try:
            police_count = await session.scalar(text("SELECT COUNT(*) FROM police_stations"))
            checks["police_stations"] = police_count or 0
        except Exception:
            checks["police_stations"] = -1
        try:
            hospital_count = await session.scalar(text("SELECT COUNT(*) FROM hospitals"))
            checks["hospitals"] = hospital_count or 0
        except Exception:
            checks["hospitals"] = -1
        try:
            ws_incidents = await session.scalar(text("SELECT COUNT(*) FROM incidents WHERE metadata->>'women_safety_category' IS NOT NULL"))
            checks["women_safety_incidents"] = ws_incidents or 0
        except Exception:
            checks["women_safety_incidents"] = -1
        checks["data_source"] = "SEED_DATA" if (checks.get("incidents", 0) or 0) > 0 else "BOOTSTRAP_FALLBACK"
    status_code = 200 if overall == "healthy" else 503 if overall == "unhealthy" else 200
    return JSONResponse(
        status_code=status_code,
        content={"status": overall, "version": settings.VERSION, "checks": checks, "timestamp": datetime.now(timezone.utc).isoformat()},
    )


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
