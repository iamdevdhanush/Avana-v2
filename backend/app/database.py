import logging
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import text
from sqlalchemy.orm import DeclarativeBase
from app.config import settings

logger = logging.getLogger(__name__)

_engine = None


def get_engine():
    global _engine
    if _engine is None:
        url = settings.build_database_url()
        if not url:
            raise RuntimeError("Database not configured. Set DATABASE_URL or POSTGRES_HOST/USER/PASSWORD.")
        _engine = create_async_engine(
            url,
            echo=settings.DEBUG,
            pool_size=15,
            max_overflow=5,
            pool_pre_ping=True,
            pool_recycle=3600,
        )
    return _engine


def get_session_factory():
    return async_sessionmaker(get_engine(), class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:
    try:
        factory = get_session_factory()
    except RuntimeError as e:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e))
    session = factory()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


async def init_db():
    engine = get_engine()
    async with engine.begin() as conn:
        # Check if alembic already manages this schema
        result = await conn.execute(
            text("SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'alembic_version')")
        )
        if result.scalar():
            result2 = await conn.execute(text("SELECT COUNT(*) FROM alembic_version"))
            if result2.scalar() and result2.scalar() > 0:
                logger.info("Database schema managed by alembic — skipping create_all")
                return
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables verified/created")


async def check_db() -> bool:
    try:
        engine = get_engine()
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return False


async def validate_schema():
    """Validate critical schema constraints at startup.
    Logs warnings for schema drift that could cause runtime errors.
    """
    engine = get_engine()
    async with engine.connect() as conn:
        tables = await conn.execute(
            text("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")
        )
        table_names = {row[0] for row in tables}

        checks = [
            ("geocoding_cache", "id", "gen_random_uuid()"),
        ]

        for table, column, expected_default in checks:
            if table not in table_names:
                logger.warning(f"Schema validation: table '{table}' does not exist")
                continue

            result = await conn.execute(
                text("""
                    SELECT column_default
                    FROM information_schema.columns
                    WHERE table_name = :table AND column_name = :column
                """),
                {"table": table, "column": column},
            )
            row = result.fetchone()
            if row is None:
                logger.warning(f"Schema validation: column '{table}.{column}' does not exist")
                continue

            actual_default = row[0] or ""
            if expected_default not in actual_default:
                logger.warning(
                    f"Schema drift detected: '{table}.{column}' "
                    f"default is '{actual_default}', expected '{expected_default}'. "
                    f"Run: alembic upgrade head"
                )
            else:
                logger.info(f"Schema OK: '{table}.{column}' has expected default")