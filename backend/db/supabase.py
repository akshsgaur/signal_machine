"""Supabase client and database operations for Signal."""

import os
from datetime import datetime, timezone

from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

_client: Client | None = None


def _get_client() -> Client:
    global _client
    if _client is None:
        url = os.environ["SUPABASE_URL"]
        key = os.environ["SUPABASE_KEY"]
        _client = create_client(url, key)
    return _client


async def store_integration_token(user_id: str, integration_type: str, token: str) -> None:
    """Upsert an OAuth/API token for a user integration."""
    client = _get_client()
    client.table("user_integrations").upsert(
        {
            "user_id": user_id,
            "integration_type": integration_type,
            "oauth_token": token,
            "connected_at": datetime.now(timezone.utc).isoformat(),
        },
        on_conflict="user_id,integration_type",
    ).execute()


async def get_integration_token(user_id: str, integration_type: str) -> str | None:
    """Retrieve a stored token for a specific integration, or None."""
    client = _get_client()
    result = (
        client.table("user_integrations")
        .select("oauth_token")
        .eq("user_id", user_id)
        .eq("integration_type", integration_type)
        .maybe_single()
        .execute()
    )
    if result.data:
        return result.data["oauth_token"]
    return None


async def get_all_tokens(user_id: str) -> dict[str, str]:
    """Return all integration tokens for a user as {integration_type: token}."""
    client = _get_client()
    result = (
        client.table("user_integrations")
        .select("integration_type,oauth_token")
        .eq("user_id", user_id)
        .execute()
    )
    return {row["integration_type"]: row["oauth_token"] for row in (result.data or [])}


async def create_pipeline_run(user_id: str, hypothesis: str, product_area: str) -> str:
    """Insert a new pipeline_runs row and return its UUID."""
    client = _get_client()
    result = (
        client.table("pipeline_runs")
        .insert(
            {
                "user_id": user_id,
                "hypothesis": hypothesis,
                "product_area": product_area,
                "status": "running",
            }
        )
        .execute()
    )
    return result.data[0]["id"]


async def update_pipeline_brief(run_id: str, brief: str, status: str) -> None:
    """Write the final brief and update run status."""
    client = _get_client()
    client.table("pipeline_runs").update(
        {
            "brief": brief,
            "status": status,
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }
    ).eq("id", run_id).execute()


async def get_pipeline_run(run_id: str) -> dict:
    """Return the full pipeline_runs row for a given UUID."""
    client = _get_client()
    result = (
        client.table("pipeline_runs")
        .select("*")
        .eq("id", run_id)
        .single()
        .execute()
    )
    return result.data
