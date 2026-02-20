"""Smoke-test Supabase DB layer. Run from backend/ with: python -m scripts.test_db"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from db.supabase import (
    store_integration_token,
    get_integration_token,
    get_all_tokens,
    create_pipeline_run,
    update_pipeline_brief,
    get_pipeline_run,
)


async def main():
    user_id = "test-user-001"

    print("1. Storing integration token...")
    await store_integration_token(user_id, "amplitude", "test-amplitude-key")
    print("   OK")

    print("2. Retrieving token...")
    token = await get_integration_token(user_id, "amplitude")
    assert token == "test-amplitude-key", f"Got: {token}"
    print(f"   OK: {token}")

    print("3. Getting all tokens...")
    tokens = await get_all_tokens(user_id)
    assert "amplitude" in tokens
    print(f"   OK: {tokens}")

    print("4. Creating pipeline run...")
    run_id = await create_pipeline_run(user_id, "Users who see feature X retain better", "Onboarding")
    print(f"   OK: run_id={run_id}")

    print("5. Fetching run...")
    run = await get_pipeline_run(run_id)
    assert run["status"] == "running"
    print(f"   OK: status={run['status']}")

    print("6. Updating brief...")
    await update_pipeline_brief(run_id, "# Decision Brief\n\nTest brief.", "complete")
    run = await get_pipeline_run(run_id)
    assert run["status"] == "complete"
    print(f"   OK: status={run['status']}")

    print("\nAll DB tests passed.")


if __name__ == "__main__":
    asyncio.run(main())
