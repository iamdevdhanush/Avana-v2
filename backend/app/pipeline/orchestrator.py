"""
Pipeline Orchestrator

Sequences agents, tracks execution, handles failures, persists run metrics.

Supported pipelines:
  • "news"       → NewsAgent → GeoAgent → RiskAgent
  • "community"  → CommunityAgent → RiskAgent
  • "risk"       → RiskAgent (recalculate only)
  • "heatmap"    → RiskAgent (heatmap only)

Usage (from admin API):
    orchestrator = PipelineOrchestrator()
    result = await orchestrator.run("news", triggered_by="admin")
"""

import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Optional

from app.agents.news_intelligence import NewsIntelligenceAgent
from app.agents.community_intelligence import CommunityIntelligenceAgent
from app.agents.geospatial_intelligence import GeospatialIntelligenceAgent
from app.agents.risk_intelligence import RiskIntelligenceAgent
from app.database import get_session_factory

logger = logging.getLogger(__name__)

_VALID_PIPELINES = frozenset({"news", "community", "risk", "heatmap"})


class PipelineOrchestrator:
    """
    Sequences the five intelligence agents and persists execution records.

    Each run is recorded in pipeline_runs table with per-step metrics,
    allowing the admin /pipeline/runs endpoint to show real observability
    rather than relying on audit_log heuristics.
    """

    def __init__(self):
        self._news_agent = NewsIntelligenceAgent()
        self._community_agent = CommunityIntelligenceAgent()
        self._geo_agent = GeospatialIntelligenceAgent()
        self._risk_agent = RiskIntelligenceAgent()

    # ──────────────────────────────────────────────────────────────────
    # Public entry point
    # ──────────────────────────────────────────────────────────────────

    async def run(
        self,
        pipeline_name: str,
        triggered_by: str = "admin",
        mock_mode: bool = False,
    ) -> dict:
        """
        Execute a named pipeline and return a structured result dict.

        Raises ValueError for unknown pipeline names.
        Never raises for agent failures — those are captured in result["steps"].
        """
        if pipeline_name not in _VALID_PIPELINES:
            raise ValueError(
                f"Unknown pipeline '{pipeline_name}'. "
                f"Valid options: {sorted(_VALID_PIPELINES)}"
            )

        run_id = str(uuid.uuid4())
        start = time.time()
        logger.info(
            f"[ORCHESTRATOR] Starting pipeline='{pipeline_name}' "
            f"run_id={run_id} triggered_by={triggered_by}"
        )

        db_run_id = await self._create_run_record(run_id, pipeline_name, triggered_by)
        steps: dict = {}

        try:
            if pipeline_name == "news":
                steps = await self._run_news_pipeline(mock_mode)
            elif pipeline_name == "community":
                steps = await self._run_community_pipeline()
            elif pipeline_name == "risk":
                steps = await self._run_risk_pipeline()
            elif pipeline_name == "heatmap":
                steps = await self._run_heatmap_pipeline()

            overall_status = (
                "failed"
                if any(
                    isinstance(v, dict) and v.get("status") == "failed"
                    for v in steps.values()
                )
                else "completed"
            )

        except Exception as exc:
            overall_status = "failed"
            steps["fatal"] = {"status": "failed", "error": str(exc)}
            logger.exception(f"[ORCHESTRATOR] Fatal error in pipeline '{pipeline_name}': {exc}")

        duration_s = round(time.time() - start, 2)
        summary = self._build_summary(pipeline_name, steps, duration_s)

        await self._complete_run_record(db_run_id, overall_status, steps, summary)

        logger.info(
            f"[ORCHESTRATOR] Pipeline '{pipeline_name}' {overall_status} "
            f"in {duration_s}s (run_id={run_id})"
        )

        return {
            "run_id": run_id,
            "pipeline": pipeline_name,
            "status": overall_status,
            "steps": steps,
            "summary": summary,
            "duration_seconds": duration_s,
            "triggered_by": triggered_by,
        }

    # ──────────────────────────────────────────────────────────────────
    # Pipeline sequences
    # ──────────────────────────────────────────────────────────────────

    async def _run_news_pipeline(self, mock_mode: bool = False) -> dict:
        """News → Geospatial → Risk"""
        steps: dict = {}

        # 1. News Intelligence
        news_result = await self._run_agent(self._news_agent, mock_mode=mock_mode)
        steps["news"] = self._extract_step_metric(news_result, "news")

        if news_result.get("status") == "failed":
            logger.error("[ORCHESTRATOR] News agent failed — aborting pipeline")
            return steps

        incidents = news_result.get("incidents", [])
        if not incidents:
            logger.info("[ORCHESTRATOR] No incidents extracted — skipping geo + risk")
            steps["geo"] = {"status": "skipped", "reason": "no_incidents"}
            steps["risk"] = {"status": "skipped", "reason": "no_incidents"}
            return steps

        # 2. Geospatial Intelligence
        geo_result = await self._run_agent(self._geo_agent, incidents=incidents)
        steps["geo"] = self._extract_step_metric(geo_result, "geo")

        if geo_result.get("saved", 0) == 0:
            logger.warning("[ORCHESTRATOR] No incidents saved — skipping risk refresh")
            steps["risk"] = {"status": "skipped", "reason": "no_saved_incidents"}
            return steps

        # 3. Risk Intelligence
        risk_result = await self._run_agent(self._risk_agent, full_heatmap=True)
        steps["risk"] = self._extract_step_metric(risk_result, "risk")

        return steps

    async def _run_community_pipeline(self) -> dict:
        """Community → Risk (if any incidents were created)"""
        steps: dict = {}

        community_result = await self._run_agent(self._community_agent)
        steps["community"] = self._extract_step_metric(community_result, "community")

        if community_result.get("verified", 0) > 0:
            risk_result = await self._run_agent(self._risk_agent, full_heatmap=False)
            steps["risk"] = self._extract_step_metric(risk_result, "risk")
        else:
            steps["risk"] = {"status": "skipped", "reason": "no_verified_reports"}

        return steps

    async def _run_risk_pipeline(self) -> dict:
        """Standalone risk recalculation."""
        risk_result = await self._run_agent(self._risk_agent, full_heatmap=False)
        return {"risk": self._extract_step_metric(risk_result, "risk")}

    async def _run_heatmap_pipeline(self) -> dict:
        """Standalone heatmap regeneration."""
        risk_result = await self._run_agent(self._risk_agent, full_heatmap=True)
        return {"heatmap": self._extract_step_metric(risk_result, "heatmap")}

    # ──────────────────────────────────────────────────────────────────
    # Agent runner — wraps each agent call with error capture
    # ──────────────────────────────────────────────────────────────────

    async def _run_agent(self, agent, **kwargs) -> dict:
        agent_name = getattr(agent, "name", type(agent).__name__)
        try:
            logger.info(f"[ORCHESTRATOR] Running agent: {agent_name}")
            result = await agent.run(**kwargs)
            return result
        except Exception as exc:
            logger.error(f"[ORCHESTRATOR] Agent '{agent_name}' raised: {exc}")
            return {"status": "failed", "error": str(exc)}

    @staticmethod
    def _extract_step_metric(result: dict, step_name: str) -> dict:
        """Flatten agent result into a compact step metric dict."""
        if result.get("status") == "failed":
            return {"status": "failed", "error": result.get("error", "unknown")}
        metrics = result.get("metrics", {})
        # Flatten nested metrics into one level
        flat: dict = {"status": "ok"}
        for key, val in metrics.items():
            if isinstance(val, dict):
                for k, v in val.items():
                    flat[f"{key}_{k}"] = v
            else:
                flat[key] = val
        # Pull up top-level counts that agents return directly
        for direct_key in ("saved", "skipped", "verified", "duplicates", "spam", "processed"):
            if direct_key in result:
                flat[direct_key] = result[direct_key]
        return flat

    # ──────────────────────────────────────────────────────────────────
    # Summary
    # ──────────────────────────────────────────────────────────────────

    @staticmethod
    def _build_summary(pipeline_name: str, steps: dict, duration_s: float) -> dict:
        summary: dict = {
            "pipeline": pipeline_name,
            "duration_seconds": duration_s,
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "failed_steps": [k for k, v in steps.items() if isinstance(v, dict) and v.get("status") == "failed"],
        }

        # Aggregate key metrics per pipeline type
        if pipeline_name == "news":
            summary["articles_fetched"] = (steps.get("news") or {}).get("fetch_count", 0)
            summary["incidents_extracted"] = (steps.get("news") or {}).get("extract_count", 0)
            summary["incidents_saved"] = (steps.get("geo") or {}).get("saved", 0)
            summary["risk_scores_updated"] = (steps.get("risk") or {}).get("risk_recalc_updated", 0)
            summary["heatmap_points"] = (steps.get("risk") or {}).get("heatmap_points_generated", 0)

        elif pipeline_name == "community":
            summary["reports_processed"] = (steps.get("community") or {}).get("processed", 0)
            summary["reports_verified"] = (steps.get("community") or {}).get("verified", 0)
            summary["reports_rejected"] = (
                (steps.get("community") or {}).get("duplicates", 0)
                + (steps.get("community") or {}).get("spam", 0)
            )

        elif pipeline_name in ("risk", "heatmap"):
            summary["risk_scores_updated"] = (steps.get("risk") or {}).get("risk_recalc_updated", 0)
            summary["heatmap_points"] = (steps.get("heatmap") or steps.get("risk") or {}).get("heatmap_points_generated", 0)

        return summary

    # ──────────────────────────────────────────────────────────────────
    # Pipeline run persistence
    # ──────────────────────────────────────────────────────────────────

    async def _create_run_record(
        self,
        run_id: str,
        pipeline_type: str,
        triggered_by: str,
    ) -> Optional[str]:
        """Insert a pipeline_runs row and return its id (or None on failure)."""
        try:
            factory = get_session_factory()
            from app.models.pipeline_run import PipelineRun
            async with factory() as session:
                run = PipelineRun(
                    id=uuid.UUID(run_id),
                    pipeline_type=pipeline_type,
                    status="running",
                    triggered_by=triggered_by,
                    steps={},
                )
                session.add(run)
                await session.commit()
            return run_id
        except Exception as exc:
            logger.warning(f"[ORCHESTRATOR] Could not create pipeline_runs record: {exc}")
            return None

    async def _complete_run_record(
        self,
        run_id: Optional[str],
        status: str,
        steps: dict,
        summary: dict,
    ) -> None:
        """Update the pipeline_runs row with final status and metrics."""
        if not run_id:
            return
        try:
            factory = get_session_factory()
            from app.models.pipeline_run import PipelineRun
            from sqlalchemy import select
            async with factory() as session:
                result = await session.execute(
                    select(PipelineRun).where(PipelineRun.id == uuid.UUID(run_id))
                )
                run = result.scalar_one_or_none()
                if run:
                    run.status = status
                    run.steps = steps
                    run.summary = summary
                    run.completed_at = datetime.now(timezone.utc)
                    run.duration_ms = int(summary.get("duration_seconds", 0) * 1000)
                    if status == "failed":
                        failed = summary.get("failed_steps", [])
                        run.error = f"Failed steps: {failed}" if failed else "Unknown error"
                    await session.commit()
        except Exception as exc:
            logger.warning(f"[ORCHESTRATOR] Could not update pipeline_runs record: {exc}")


# Singleton for import convenience
orchestrator = PipelineOrchestrator()
