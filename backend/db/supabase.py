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


async def get_slack_tokens(user_id: str) -> list[dict]:
    """Return Slack tokens for a user as [{team_id, token}]."""
    client = _get_client()
    result = (
        client.table("user_integrations")
        .select("integration_type,oauth_token")
        .eq("user_id", user_id)
        .like("integration_type", "slack:%")
        .execute()
    )
    tokens = []
    for row in result.data or []:
        integration_type = row.get("integration_type", "")
        team_id = integration_type.split("slack:")[-1] if "slack:" in integration_type else ""
        tokens.append({"team_id": team_id, "token": row.get("oauth_token")})
    return tokens


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


async def get_latest_pipeline_run(user_id: str) -> dict | None:
    """Return the most recent completed pipeline run for a user."""
    client = _get_client()
    result = (
        client.table("pipeline_runs")
        .select("*")
        .eq("user_id", user_id)
        .eq("status", "complete")
        .order("completed_at", desc=True)
        .limit(1)
        .execute()
    )
    rows = result.data or []
    return rows[0] if rows else None


async def create_chat_session(user_id: str, title: str | None = None) -> str:
    """Create a chat session and return its UUID."""
    client = _get_client()
    result = (
        client.table("chat_sessions")
        .insert({"user_id": user_id, "title": title})
        .execute()
    )
    return result.data[0]["id"]


async def add_chat_message(
    session_id: str,
    role: str,
    content: str,
    sources_used: list[str] | None = None,
) -> None:
    """Insert a message into chat_messages."""
    client = _get_client()
    payload = {
        "session_id": session_id,
        "role": role,
        "content": content,
        "sources_used": sources_used or [],
    }
    client.table("chat_messages").insert(payload).execute()


async def touch_chat_session(session_id: str) -> None:
    """Update chat session timestamp."""
    client = _get_client()
    client.table("chat_sessions").update(
        {"updated_at": datetime.now(timezone.utc).isoformat()}
    ).eq("id", session_id).execute()


async def list_chat_sessions(user_id: str, limit: int = 20) -> list[dict]:
    """Return recent chat sessions for a user."""
    client = _get_client()
    result = (
        client.table("chat_sessions")
        .select("id,title,created_at,updated_at")
        .eq("user_id", user_id)
        .order("updated_at", desc=True)
        .limit(limit)
        .execute()
    )
    return result.data or []


async def list_chat_messages(session_id: str, limit: int = 200) -> list[dict]:
    """Return chat messages for a session."""
    client = _get_client()
    result = (
        client.table("chat_messages")
        .select("id,role,content,sources_used,created_at")
        .eq("session_id", session_id)
        .order("created_at", desc=False)
        .limit(limit)
        .execute()
    )
    return result.data or []


async def get_user_id_for_slack_team(team_id: str) -> str | None:
    """Return the Signal user_id associated with a Slack workspace install."""
    client = _get_client()
    result = (
        client.table("user_integrations")
        .select("user_id")
        .eq("integration_type", f"slack:{team_id}")
        .maybe_single()
        .execute()
    )
    if result.data:
        return result.data["user_id"]
    return None


async def store_slack_message(
    user_id: str,
    team_id: str,
    channel_id: str,
    slack_user_id: str,
    text: str,
    ts: str,
    thread_ts: str | None,
    is_dm: bool,
    raw: dict,
) -> None:
    """Insert a Slack message into slack_messages."""
    client = _get_client()
    payload = {
        "user_id": user_id,
        "team_id": team_id,
        "channel_id": channel_id,
        "slack_user_id": slack_user_id,
        "text": text,
        "ts": ts,
        "thread_ts": thread_ts,
        "is_dm": is_dm,
        "raw": raw,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    client.table("slack_messages").insert(payload).execute()


async def query_slack_messages(
    user_id: str,
    since: str | None = None,
    until: str | None = None,
    channel_id: str | None = None,
    slack_user_id: str | None = None,
    team_id: str | None = None,
    limit: int = 200,
) -> list[dict]:
    """Query stored Slack messages for a user."""
    client = _get_client()
    query = client.table("slack_messages").select(
        "id,team_id,channel_id,slack_user_id,text,ts,thread_ts,is_dm,created_at"
    ).eq("user_id", user_id)
    if team_id:
        query = query.eq("team_id", team_id)
    if channel_id:
        query = query.eq("channel_id", channel_id)
    if slack_user_id:
        query = query.eq("slack_user_id", slack_user_id)
    if since:
        query = query.gte("created_at", since)
    if until:
        query = query.lte("created_at", until)
    result = query.order("created_at", desc=True).limit(limit).execute()
    return result.data or []
