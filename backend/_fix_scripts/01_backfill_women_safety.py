"""
PHASE 2: Backfill women_safety_category for all historical incidents.

Maps existing incident_type values to women_safety categories.
Incidents that match women-safety crime types get their category set.
Non-women-safety incidents (THEFT, BURGLARY, ROBBERY, RIOT, VANDALISM, TRAFFIC_ACCIDENT)
are left with NULL (excluded from risk/heatmap).

Run: python _fix_scripts/01_backfill_women_safety.py
"""
import asyncio
import sys
sys.path.insert(0, '.')
from app.database import get_session_factory
from app.pipeline.women_safety import (
    WOMEN_SAFETY_CATEGORIES, INCIDENT_TYPE_TO_WOMEN_SAFETY,
    get_women_safety_details, is_women_safety_category,
)
from sqlalchemy import text

BACKFILL_MAP = {
    # IncidentType (UPPER) -> (women_safety_category, tier)
    "RAPE": ("Rape", 1),
    "ASSAULT": ("Assault Against Women", 2),
    "HARASSMENT": ("Sexual Harassment", 1),
    "STALKING": ("Stalking", 1),
    "DOMESTIC_VIOLENCE": ("Domestic Violence", 2),
    "KIDNAPPING": ("Kidnapping of Women", 1),
    "MURDER": ("Murder of Women", 2),
    "ROBBERY": ("Chain Snatching", 3),
    # Non-women-safety: leave AS IS (women_safety_category stays NULL)
    # THEFT, BURGLARY, RIOT, VANDALISM, TRAFFIC_ACCIDENT, PICKPOCKETING, SUSPICIOUS_ACTIVITY, OTHER
}

async def backfill():
    factory = get_session_factory()
    async with factory() as session:
        # Count before
        total = await session.scalar(text("SELECT COUNT(*) FROM incidents"))
        ws_null = await session.scalar(text(
            "SELECT COUNT(*) FROM incidents WHERE metadata->>'women_safety_category' IS NULL"
        ))
        ws_set = await session.scalar(text(
            "SELECT COUNT(*) FROM incidents WHERE metadata->>'women_safety_category' IS NOT NULL"
        ))
        print(f"Before: {total} total, {ws_null} NULL, {ws_set} set")

        updated = 0
        for itype, (ws_cat, tier) in BACKFILL_MAP.items():
            _, risk_weight, sev_weight, base_sev = get_women_safety_details(ws_cat)

            result = await session.execute(
                text("""
                    UPDATE incidents
                    SET metadata = jsonb_set(
                            jsonb_set(
                                COALESCE(metadata, '{}'::jsonb),
                                '{women_safety_category}', :cat_q
                            ),
                            '{women_safety_weight}', :wt_q
                        )
                    WHERE incident_type::text = :itype
                      AND (metadata->>'women_safety_category' IS NULL OR metadata->>'women_safety_category' = '')
                """),
                {
                    "itype": itype,
                    "cat_q": f'"{ws_cat}"',
                    "wt_q": str(sev_weight),
                }
            )
            cnt = result.rowcount
            if cnt > 0:
                print(f"  {itype} -> {ws_cat} (tier {tier}, weight {sev_weight}): {cnt} records")
                updated += cnt

        # Verify after
        await session.commit()
        total2 = await session.scalar(text("SELECT COUNT(*) FROM incidents"))
        ws_set2 = await session.scalar(text(
            "SELECT COUNT(*) FROM incidents WHERE metadata->>'women_safety_category' IS NOT NULL"
        ))
        ws_null2 = await session.scalar(text(
            "SELECT COUNT(*) FROM incidents WHERE metadata->>'women_safety_category' IS NULL"
        ))
        print(f"\nAfter: {total2} total, {ws_null2} NULL, {ws_set2} set (updated={updated})")

        # Show remaining unclassified
        if ws_null2 > 0:
            result = await session.execute(text("""
                SELECT incident_type, COUNT(*) as cnt
                FROM incidents
                WHERE metadata->>'women_safety_category' IS NULL
                GROUP BY incident_type ORDER BY cnt DESC
            """))
            print(f"\nRemaining unclassified ({ws_null2} records):")
            for r in result.fetchall():
                print(f"  {r[0]}: {r[1]} - intentionally excluded from women-safety pipeline")

asyncio.run(backfill())
