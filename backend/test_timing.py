"""
Test script to run the news pipeline and capture timing output.
Loads .env into os.environ aggressively before any app imports.
"""
import asyncio
import logging
import os
import sys

# Force-load .env into process environment before anything
env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
if os.path.exists(env_path):
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ[k.strip()] = v.strip()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)

sys.path.insert(0, "backend")

from app.pipeline.orchestrator import PipelineOrchestrator
from app.utils.timing import Timer


async def main():
    o = PipelineOrchestrator()
    with Timer("FULL TEST: Pipeline Orchestration"):
        result = await o.run("news", triggered_by="test_timing")

    print("\n" + "=" * 60)
    print("FINAL RESULT")
    print("=" * 60)
    print(f"Status:   {result['status']}")
    print(f"Duration: {result['duration_seconds']:.2f}s")
    print(f"Steps:    {list(result['steps'].keys())}")
    for k, v in result["steps"].items():
        print(f"  {k}: {v}")
    print(f"Summary: {result.get('summary', {})}")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
