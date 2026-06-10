import asyncio
import logging
from datetime import datetime, timezone
from celery.schedules import crontab
from app.tasks.celery_app import celery_app
from app.database import async_session_factory
from sqlalchemy import text

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def run_news_agent(self):
    logger.info("Starting scheduled news intelligence agent")
    try:
        from app.agents.news_intelligence import run_scheduled
        result = run_scheduled()
        logger.info(f"News agent completed: {result.get('saved_count', 0)} incidents saved")
        return result
    except Exception as e:
        logger.error(f"News agent failed: {e}")
        raise self.retry(exc=e)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=30)
def run_community_agent(self):
    logger.info("Starting scheduled community intelligence agent")
    try:
        from app.agents.community_intelligence import run_scheduled
        result = run_scheduled()
        logger.info(f"Community agent completed: {result.get('saved_count', 0)} processed")
        return result
    except Exception as e:
        logger.error(f"Community agent failed: {e}")
        raise self.retry(exc=e)


@celery_app.task(bind=True, max_retries=2, default_retry_delay=120)
def update_heatmaps(self):
    logger.info("Starting scheduled heatmap updates")
    results = {}
    districts = [
        "Bengaluru Urban", "Bengaluru Rural", "Mysuru", "Dakshina Kannada",
        "Belagavi", "Dharwad", "Hubballi", "Mangaluru", "Udupi",
        "Shivamogga", "Tumakuru", "Hassan", "Mandya", "Chikkamagaluru",
        "Ballari", "Kalaburagi", "Vijayapura", "Raichur",
    ]
    for district in districts:
        try:
            from app.agents.heatmap import generate_heatmap
            result = asyncio.run(generate_heatmap(zoom_level="district", district=district))
            results[district] = {
                "status": "completed",
                "points": len(result.get("heatmap_data", [])),
            }
            logger.info(f"Heatmap updated for {district}")
        except Exception as e:
            logger.error(f"Heatmap update failed for {district}: {e}")
            results[district] = {"status": "failed", "error": str(e)}
    return results


@celery_app.task(bind=True, max_retries=2, default_retry_delay=60)
def calculate_risk_scores(self):
    logger.info("Starting batch risk score recalculation")
    try:
        from app.agents.risk_scoring import batch_calculate
        result = asyncio.run(batch_calculate(stale_only=True))
        logger.info(f"Risk score calculation completed: {result}")
        return result
    except Exception as e:
        logger.error(f"Risk score calculation failed: {e}")
        raise self.retry(exc=e)


@celery_app.task
def cleanup_old_data():
    logger.info("Starting data cleanup")
    results = {}
    try:
        import asyncio

        async def _cleanup():
            async with async_session_factory() as session:
                cutoff = datetime.now(timezone.utc)
                try:
                    audit_result = await session.execute(
                        text("""
                            DELETE FROM audit_logs
                            WHERE created_at < :cutoff
                        """),
                        {"cutoff": cutoff},
                    )
                    results["audit_logs_deleted"] = audit_result.rowcount
                except Exception as e:
                    logger.error(f"Audit log cleanup error: {e}")
                    results["audit_logs_error"] = str(e)
                try:
                    session_result = await session.execute(
                        text("""
                            DELETE FROM user_sessions
                            WHERE expires_at < NOW()
                        """)
                    )
                    results["stale_sessions_deleted"] = session_result.rowcount
                except Exception as e:
                    logger.error(f"Session cleanup error: {e}")
                    results["stale_sessions_error"] = str(e)
                try:
                    news_result = await session.execute(
                        text("""
                            UPDATE news_articles
                            SET archived = true
                            WHERE published_at < :cutoff AND archived = false
                        """),
                        {"cutoff": cutoff},
                    )
                    results["news_articles_archived"] = news_result.rowcount
                except Exception as e:
                    logger.error(f"News article archive error: {e}")
                    results["news_articles_error"] = str(e)
                await session.commit()

        asyncio.run(_cleanup())
        logger.info(f"Cleanup completed: {results}")
        return results
    except Exception as e:
        logger.error(f"Cleanup failed: {e}")
        return {"error": str(e)}


@celery_app.task(bind=True, max_retries=2, default_retry_delay=300)
def run_all_agents(self):
    logger.info("Starting all agents")
    results = {}
    try:
        news_result = run_news_agent.delay()
        results["news"] = news_result.id
    except Exception as e:
        logger.error(f"Failed to trigger news agent: {e}")
        results["news_error"] = str(e)
    try:
        community_result = run_community_agent.delay()
        results["community"] = community_result.id
    except Exception as e:
        logger.error(f"Failed to trigger community agent: {e}")
        results["community_error"] = str(e)
    try:
        heatmap_result = update_heatmaps.delay()
        results["heatmap"] = heatmap_result.id
    except Exception as e:
        logger.error(f"Failed to trigger heatmap update: {e}")
        results["heatmap_error"] = str(e)
    try:
        risk_result = calculate_risk_scores.delay()
        results["risk_scores"] = risk_result.id
    except Exception as e:
        logger.error(f"Failed to trigger risk score calculation: {e}")
        results["risk_scores_error"] = str(e)
    return results


def setup_periodic_tasks():
    celery_app.conf.beat_schedule = {
        "run-news-agent-every-6-hours": {
            "task": "app.tasks.scheduled.run_news_agent",
            "schedule": crontab(hour="*/6"),
            "options": {"queue": "agents"},
        },
        "run-community-agent-every-hour": {
            "task": "app.tasks.scheduled.run_community_agent",
            "schedule": crontab(minute="0"),
            "options": {"queue": "agents"},
        },
        "update-heatmaps-every-2-hours": {
            "task": "app.tasks.scheduled.update_heatmaps",
            "schedule": crontab(hour="*/2"),
            "options": {"queue": "heatmap"},
        },
        "calculate-risk-scores-every-6-hours": {
            "task": "app.tasks.scheduled.calculate_risk_scores",
            "schedule": crontab(hour="*/6"),
            "options": {"queue": "scoring"},
        },
        "cleanup-old-data-daily": {
            "task": "app.tasks.scheduled.cleanup_old_data",
            "schedule": crontab(hour="3", minute="0"),
            "options": {"queue": "maintenance"},
        },
        "run-all-agents-every-12-hours": {
            "task": "app.tasks.scheduled.run_all_agents",
            "schedule": crontab(hour="*/12"),
            "options": {"queue": "agents"},
        },
    }
    logger.info("Periodic tasks registered with celery beat")
