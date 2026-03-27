"""Smoke-test the full pipeline with a hardcoded hypothesis.

Run from backend/ with: python -m scripts.test_pipeline
Requires DATABASE_URL and ANTHROPIC_API_KEY in .env
"""

import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from db.supabase import create_pipeline_run, get_pipeline_run
from agents.pipeline import run_signal_pipeline, AGENT_FILE_MAP


async def main():
    user_id = "test-user-001"
    hypothesis = "Users who complete onboarding in under 5 minutes have 2x 30-day retention"
    product_area = "Onboarding"

    print(f"Creating pipeline run for hypothesis: {hypothesis}")
    run_id = await create_pipeline_run(user_id, hypothesis, product_area)
    print(f"  run_id: {run_id}")

    print("Running pipeline...")
    await run_signal_pipeline(run_id, user_id, hypothesis, product_area)

    print("Checking output files...")
    storage = Path("storage/files") / run_id
    for agent, file_path in AGENT_FILE_MAP.items():
        disk_path = storage / file_path
        exists = disk_path.exists()
        print(f"  {agent}: {'OK' if exists else 'MISSING'} → {disk_path}")

    brief_path = storage / "output/decision_brief.md"
    print(f"  decision_brief: {'OK' if brief_path.exists() else 'MISSING'}")

    run = await get_pipeline_run(run_id)
    print(f"\nFinal status: {run['status']}")
    print(f"Brief preview (first 200 chars):\n{(run.get('brief') or '')[:200]}")


if __name__ == "__main__":
    asyncio.run(main())
