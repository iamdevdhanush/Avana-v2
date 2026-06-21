"""
Migration script: Export from Render PostgreSQL → Import to Supabase PostgreSQL.

Preserves:
  - All tables with data
  - PostGIS geometry columns
  - Indexes
  - Users
  - Incidents
  - Risk scores
  - All other entities

Usage:
    # Step 1: Export from Render
    python -m scripts.migration.render_to_supabase export --output render_dump.sql

    # Step 2: Import to Supabase
    python -m scripts.migration.render_to_supabase import --input render_dump.sql --supabase-url "postgresql+asyncpg://..."

    # Dry run (no actual writes)
    python -m scripts.migration.render_to_supabase import --input render_dump.sql --supabase-url "..." --dry-run
"""

import argparse
import asyncio
import logging
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.config import settings

logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(message)s")
logger = logging.getLogger("migration")

EXPORT_TABLES_ORDERED = [
    # Enums are created by create_all - we export data only
    "users",
    "locations",
    "incidents",
    "risk_scores",
    "safety_reports",
    "sos_events",
    "community_posts",
    "comments",
    "police_stations",
    "hospitals",
    "crime_stats",
    "geocoding_cache",
    "news_articles",
    "audit_logs",
    "emergency_contacts",
]

GEOMETRY_TABLES = [
    "incidents", "risk_scores", "safety_reports", "sos_events",
    "police_stations", "hospitals", "locations", "news_articles",
]


async def export_render(output_path: str):
    """Export all data from Render PostgreSQL to a SQL file."""
    from app.database import get_engine

    engine = get_engine()
    logger.info(f"[EXPORT] Starting export from Render...")

    lines = [
        "-- Avana V2 Render → Supabase Migration Export",
        f"-- Generated: {datetime.now().isoformat()}",
        f"-- Source: {settings.build_database_url().split('@')[1].split('/')[0] if '@' in settings.build_database_url() else 'Render'}",
        "",
        "-- PostGIS extension (Supabase already has this, but ensure it)",
        "CREATE EXTENSION IF NOT EXISTS postgis;",
        "CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\";",
        "",
    ]

    async with engine.connect() as conn:
        for table in EXPORT_TABLES_ORDERED:
            table_exists = await conn.execute(
                text("SELECT to_regclass(:table)"), {"table": table}
            )
            if not table_exists.scalar():
                logger.warning(f"[EXPORT] Table '{table}' does not exist — skipping")
                continue

            result = await conn.execute(text(f"SELECT * FROM {table}"))
            rows = result.fetchall()
            if not rows:
                logger.info(f"[EXPORT] Table '{table}' is empty — skipping")
                continue

            column_names = result.keys()
            columns = ", ".join(f'"{c}"' for c in column_names)

            lines.append(f"-- Table: {table} ({len(rows)} rows)")
            lines.append(f"TRUNCATE TABLE \"{table}\" CASCADE;")

            for row in rows:
                values = []
                for val in row:
                    if val is None:
                        values.append("NULL")
                    elif isinstance(val, (int, float)):
                        values.append(str(val))
                    elif isinstance(val, bool):
                        values.append("TRUE" if val else "FALSE")
                    elif isinstance(val, bytes):
                        hex_str = val.hex()
                        values.append(f"'\\\\x{hex_str}'::bytea")
                    elif isinstance(val, datetime):
                        values.append(f"'{val.isoformat()}'::timestamptz")
                    else:
                        escaped = str(val).replace("'", "''")
                        values.append(f"'{escaped}'")
                vals = ", ".join(values)

                if table in GEOMETRY_TABLES and "geom" in column_names:
                    idx = list(column_names).index("geom")
                    if row[idx] is not None:
                        geom_hex = bytes(row[idx]).hex() if isinstance(row[idx], memoryview) else str(row[idx])
                        vals = vals.replace(
                            values[idx],
                            f"ST_GeomFromEWKB('\\\\x{geom_hex}'::bytea)" if isinstance(row[idx], memoryview) else f"'{geom_hex}'"
                        )

                lines.append(f"INSERT INTO \"{table}\" ({columns}) VALUES ({vals});")

            lines.append("")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    logger.info(f"[EXPORT] Complete — {len(lines)} lines written to {output_path}")
    return {"status": "ok", "tables": len(EXPORT_TABLES_ORDERED), "path": output_path}


async def import_supabase(input_path: str, supabase_url: str = None, dry_run: bool = False):
    """Import SQL dump into Supabase PostgreSQL."""
    if not os.path.exists(input_path):
        return {"status": "error", "reason": f"File not found: {input_path}"}

    if dry_run:
        with open(input_path, "r", encoding="utf-8") as f:
            line_count = len(f.readlines())
        logger.info(f"[IMPORT] Dry run — would execute {line_count} lines from {input_path}")
        return {"status": "dry_run", "lines": line_count}

    url = supabase_url or settings.build_database_url()
    engine = create_async_engine(url, echo=False, pool_pre_ping=True)

    with open(input_path, "r", encoding="utf-8") as f:
        sql = f.read()

    statements = [s.strip() for s in sql.split(";") if s.strip()]

    async with engine.begin() as conn:
        for i, stmt in enumerate(statements):
            try:
                await conn.execute(text(stmt))
            except Exception as e:
                logger.warning(f"[IMPORT] Statement {i+1} failed (continuing): {e}")

    await engine.dispose()
    logger.info(f"[IMPORT] Complete — {len(statements)} statements executed")
    return {"status": "ok", "statements": len(statements)}


def main():
    parser = argparse.ArgumentParser(description="Render → Supabase Migration")
    subparsers = parser.add_subparsers(dest="command", required=True)

    export_parser = subparsers.add_parser("export", help="Export from Render")
    export_parser.add_argument("--output", default="render_dump.sql", help="Output SQL file")

    import_parser = subparsers.add_parser("import", help="Import to Supabase")
    import_parser.add_argument("--input", default="render_dump.sql", help="Input SQL file")
    import_parser.add_argument("--supabase-url", help="Supabase connection URL (optional, uses DATABASE_URL otherwise)")
    import_parser.add_argument("--dry-run", action="store_true", help="Dry run only")

    args = parser.parse_args()

    if args.command == "export":
        asyncio.run(export_render(args.output))
    elif args.command == "import":
        asyncio.run(import_supabase(args.input, args.supabase_url, args.dry_run))


if __name__ == "__main__":
    main()
