"""Audit risk scores and women_safety coverage after fixes."""
import asyncio
import sys
sys.path.insert(0, '.')
from app.database import get_session_factory
from sqlalchemy import text

async def audit():
    factory = get_session_factory()
    async with factory() as session:
        # Risk score distribution
        r = await session.execute(text("""
            SELECT category, COUNT(*), ROUND(AVG(score)::numeric, 2),
                   ROUND(MIN(score)::numeric, 2), ROUND(MAX(score)::numeric, 2)
            FROM risk_scores GROUP BY category ORDER BY AVG(score) DESC
        """))
        print("=== RISK SCORE DISTRIBUTION ===")
        for row in r.fetchall():
            print(f'  {row[0]}: {row[1]} rows, avg={row[2]} min={row[3]} max={row[4]}')

        # Total counts
        total = await session.scalar(text("SELECT COUNT(*) FROM risk_scores"))
        print(f'\nTotal risk_scores: {total}')

        # Women-safety coverage
        total_inc = await session.scalar(text("SELECT COUNT(*) FROM incidents"))
        ws_set = await session.scalar(text(
            "SELECT COUNT(*) FROM incidents WHERE metadata->>'women_safety_category' IS NOT NULL"
        ))
        ws_null = await session.scalar(text(
            "SELECT COUNT(*) FROM incidents WHERE metadata->>'women_safety_category' IS NULL"
        ))
        print(f'\n=== WOMEN-SAFETY COVERAGE ===')
        print(f'  Total incidents: {total_inc}')
        print(f'  Classified: {ws_set} ({ws_set/total_inc*100:.1f}%)')
        print(f'  Excluded: {ws_null} ({ws_null/total_inc*100:.1f}%)')

        # Category breakdown
        r = await session.execute(text("""
            SELECT metadata->>'women_safety_category' as cat,
                   metadata->>'women_safety_weight' as wt,
                   COUNT(*) as cnt
            FROM incidents
            WHERE metadata->>'women_safety_category' IS NOT NULL
            GROUP BY cat, wt ORDER BY cnt DESC
        """))
        print(f'\n=== CATEGORY BREAKDOWN ===')
        for row in r.fetchall():
            print(f'  {row[0]} (weight={row[1]}): {row[2]}')

        # Women safety coverage percentage
        coverage = (ws_set / total_inc * 100) if total_inc else 0
        print(f'\n  Women-safety coverage: {coverage:.1f}%')

        # Non-women-safety excluded types
        r = await session.execute(text("""
            SELECT incident_type, COUNT(*) FROM incidents
            WHERE metadata->>'women_safety_category' IS NULL
            GROUP BY incident_type ORDER BY COUNT(*) DESC
        """))
        print(f'\n=== EXCLUDED TYPES (no women_safety_category) ===')
        for row in r.fetchall():
            print(f'  {row[0]}: {row[1]}')

asyncio.run(audit())
