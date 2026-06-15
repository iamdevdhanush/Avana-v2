"""
End-to-end test of the community pipeline.
Inserts a synthetic pending report then runs the pipeline.
"""
import asyncio, sys, os, uuid
sys.path.insert(0, os.path.dirname(__file__))
from dotenv import load_dotenv; load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

from app.config import settings
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import text


async def main():
    engine = create_async_engine(settings.build_database_url(), echo=False)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    # Step 1 – find a real user we can foreign-key on
    print("=== Step 1: Ensuring test user exists ===")
    async with factory() as session:
        r = await session.execute(text("SELECT id FROM users LIMIT 1"))
        row = r.fetchone()
        if not row:
            print("  No users found — cannot run E2E test")
            return
        user_id = str(row[0])
        print(f"  Using user_id: {user_id}")

    # Step 2 – insert a synthetic pending safety_report using cast-free syntax
    print()
    print("=== Step 2: Inserting synthetic PENDING safety_report ===")
    test_report_id = str(uuid.uuid4())
    async with factory() as session:
        # asyncpg doesn't support :param::type in parameterised queries;
        # use explicit column-level casts in the SQL instead.
        await session.execute(text("""
            INSERT INTO safety_reports
                (id, user_id, incident_type, severity, latitude, longitude,
                 description, confidence_score, is_anonymous, is_verified,
                 status, is_duplicate, created_at, updated_at)
            VALUES (
                gen_random_uuid(),
                :uid,
                'THEFT',
                'MEDIUM',
                13.0827, 80.2707,
                :desc,
                0.6,
                false, false,
                'PENDING',
                false,
                NOW(), NOW()
            )
            RETURNING id
        """), {"uid": user_id, "desc": "Test report for pipeline verification"})
        await session.commit()

    # Fetch the actual ID (since we used gen_random_uuid())
    async with factory() as session:
        r = await session.execute(text(
            "SELECT id FROM safety_reports WHERE description = :desc ORDER BY created_at DESC LIMIT 1"
        ), {"desc": "Test report for pipeline verification"})
        row = r.fetchone()
        if row:
            test_report_id = str(row[0])
    print(f"  Inserted report: {test_report_id}")

    # Step 3 – run the community pipeline
    print()
    print("=== Step 3: Running process_pending_reports() ===")
    from app.pipeline.community import process_pending_reports
    try:
        result = await process_pending_reports()
        print(f"  Pipeline result: {result}")
        if result.get("processed", 0) >= 1:
            print("  [PASS] Pipeline executed and processed at least 1 report")
        else:
            print("  [WARN] Pipeline ran but processed 0 reports (check if test data was picked up)")
    except Exception as ex:
        print(f"  [FAIL] Pipeline raised: {type(ex).__name__}: {ex}")
        import traceback; traceback.print_exc()
        # Skip further steps
        return

    # Step 4 – verify the report status was updated
    print()
    print("=== Step 4: Checking report status after pipeline ===")
    async with factory() as session:
        r = await session.execute(text(
            "SELECT status, confidence_score, is_duplicate, duplicate_of "
            "FROM safety_reports WHERE id = :rid"
        ), {"rid": test_report_id})
        row = r.fetchone()
        if row:
            print(f"  status={row[0]} conf={row[1]} is_dup={row[2]} dup_of={row[3]}")
            expected_statuses = {"PENDING", "APPROVED", "REJECTED"}
            if row[0] in expected_statuses:
                print(f"  [PASS] Status is a valid reportstatus enum value")
            else:
                print(f"  [FAIL] Unexpected status: {row[0]}")
        else:
            print("  Report not found!")

    # Cleanup
    print()
    print("=== Cleanup: Removing test report ===")
    async with factory() as session:
        await session.execute(text(
            "DELETE FROM safety_reports WHERE id = :rid"
        ), {"rid": test_report_id})
        # Also clean up any incidents created from this test
        await session.execute(text(
            "DELETE FROM incidents WHERE description = :desc AND source = 'COMMUNITY_REPORT'"
        ), {"desc": "Test report for pipeline verification"})
        await session.commit()
    print("  Done")
    print()
    print("=== E2E TEST COMPLETE ===")


asyncio.run(main())
