"""Database operations for Signal on plain Postgres/Ghost.

This module intentionally keeps the historical filename to avoid a broad import
rename while the storage backend moves away from Supabase.
"""

from __future__ import annotations

import asyncio
import os
from datetime import datetime, timezone
from typing import Any, Sequence

from dotenv import load_dotenv

from integrations.registry import coerce_credentials, get_provider

load_dotenv()

AIRBYTE_METADATA_KEY = "_airbyte"
PROVIDER_BACKEND_KEY = "_provider_backend"
RUNTIME_READY_KEY = "_runtime_ready"


def _require_database_url() -> str:
    database_url = os.getenv("DATABASE_URL", "").strip()
    if not database_url:
        raise RuntimeError("DATABASE_URL is not configured.")
    return database_url


def _connect():
    try:
        import psycopg
        from psycopg.rows import dict_row
    except ImportError as exc:
        raise RuntimeError(
            "psycopg is required for the Ghost/Postgres backend. "
            "Install backend dependencies after updating requirements."
        ) from exc
    conn = psycopg.connect(_require_database_url(), row_factory=dict_row)
    conn.autocommit = True
    return conn


def _fetch_all_sync(query: str, params: Sequence[Any] | None = None) -> list[dict[str, Any]]:
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(query, params or ())
        rows = cur.fetchall()
    return [dict(row) for row in rows]


def _fetch_one_sync(query: str, params: Sequence[Any] | None = None) -> dict[str, Any] | None:
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(query, params or ())
        row = cur.fetchone()
    return dict(row) if row is not None else None


def _execute_sync(query: str, params: Sequence[Any] | None = None) -> None:
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(query, params or ())


async def fetch_all(query: str, params: Sequence[Any] | None = None) -> list[dict[str, Any]]:
    return await asyncio.to_thread(_fetch_all_sync, query, params)


async def fetch_one(query: str, params: Sequence[Any] | None = None) -> dict[str, Any] | None:
    return await asyncio.to_thread(_fetch_one_sync, query, params)


async def execute(query: str, params: Sequence[Any] | None = None) -> None:
    await asyncio.to_thread(_execute_sync, query, params)


async def store_integration_credentials(
    user_id: str,
    integration_type: str,
    credentials: dict[str, Any],
    oauth_token: str | None = None,
) -> None:
    """Upsert structured credentials for a user integration."""
    token_value = oauth_token
    if token_value is None:
        simple_secret_keys = ("token", "api_key", "api_token", "pat_secret", "value")
        for key in simple_secret_keys:
            value = credentials.get(key)
            if isinstance(value, str) and value.strip():
                token_value = value.strip()
                break
    await execute(
        """
        INSERT INTO user_integrations (
            user_id, integration_type, oauth_token, credentials_json, connected_at, updated_at
        )
        VALUES (%s, %s, %s, %s::jsonb, %s, %s)
        ON CONFLICT (user_id, integration_type)
        DO UPDATE SET
            oauth_token = EXCLUDED.oauth_token,
            credentials_json = EXCLUDED.credentials_json,
            connected_at = EXCLUDED.connected_at,
            updated_at = EXCLUDED.updated_at
        """,
        (
            user_id,
            integration_type,
            token_value,
            _json_dumps(credentials),
            datetime.now(timezone.utc),
            datetime.now(timezone.utc),
        ),
    )


async def store_workspace_integration_credentials(
    workspace_id: str,
    integration_type: str,
    credentials: dict[str, Any],
    oauth_token: str | None = None,
) -> None:
    """Upsert structured credentials for a workspace integration."""
    await execute(
        """
        INSERT INTO workspace_integrations (
            workspace_id, integration_type, oauth_token, credentials_json, connected_at, updated_at
        )
        VALUES (%s, %s, %s, %s::jsonb, %s, %s)
        ON CONFLICT (workspace_id, integration_type)
        DO UPDATE SET
            oauth_token = EXCLUDED.oauth_token,
            credentials_json = EXCLUDED.credentials_json,
            connected_at = EXCLUDED.connected_at,
            updated_at = EXCLUDED.updated_at
        """,
        (
            workspace_id,
            integration_type,
            oauth_token,
            _json_dumps(credentials),
            datetime.now(timezone.utc),
            datetime.now(timezone.utc),
        ),
    )


async def store_integration_token(user_id: str, integration_type: str, token: str) -> None:
    credentials = coerce_credentials(integration_type, token) or {"token": token}
    await store_integration_credentials(
        user_id,
        integration_type,
        credentials,
        oauth_token=token,
    )


async def get_integration_token(user_id: str, integration_type: str) -> str | None:
    row = await fetch_one(
        """
        SELECT oauth_token
        FROM user_integrations
        WHERE user_id = %s AND integration_type = %s
        """,
        (user_id, integration_type),
    )
    if row:
        return row.get("oauth_token")
    return None


def _normalize_stored_credentials(
    integration_type: str,
    oauth_token: str | None,
    credentials_json: Any,
) -> dict[str, Any]:
    if isinstance(credentials_json, dict):
        return credentials_json
    return coerce_credentials(integration_type, oauth_token) or {}


def _is_airbyte_metadata(credentials_json: Any) -> bool:
    return isinstance(credentials_json, dict) and credentials_json.get(PROVIDER_BACKEND_KEY) == "airbyte_cloud"


def _build_airbyte_record_payload(
    airbyte: dict[str, Any],
    *,
    runtime_ready: bool = False,
) -> dict[str, Any]:
    return {
        PROVIDER_BACKEND_KEY: "airbyte_cloud",
        RUNTIME_READY_KEY: runtime_ready,
        AIRBYTE_METADATA_KEY: airbyte,
    }


async def get_all_integration_credentials(user_id: str) -> dict[str, dict[str, Any]]:
    rows = await fetch_all(
        """
        SELECT integration_type, oauth_token, credentials_json
        FROM user_integrations
        WHERE user_id = %s
        """,
        (user_id,),
    )
    data: dict[str, dict[str, Any]] = {}
    for row in rows:
        integration_type = row["integration_type"]
        credentials_json = row.get("credentials_json")
        if _is_airbyte_metadata(credentials_json):
            runtime_ready = bool(credentials_json.get(RUNTIME_READY_KEY))
            provider = get_provider(integration_type)
            if provider and provider.runtime_ready:
                runtime_ready = True
            if not runtime_ready:
                continue
        data[integration_type] = _normalize_stored_credentials(
            integration_type,
            row.get("oauth_token"),
            credentials_json,
        )
    return data


async def list_integration_records(user_id: str) -> list[dict[str, Any]]:
    return await fetch_all(
        """
        SELECT integration_type, oauth_token, credentials_json, connected_at, updated_at
        FROM user_integrations
        WHERE user_id = %s
        """,
        (user_id,),
    )


async def list_workspace_integration_records(workspace_id: str) -> list[dict[str, Any]]:
    return await fetch_all(
        """
        SELECT integration_type, oauth_token, credentials_json, connected_at, updated_at
        FROM workspace_integrations
        WHERE workspace_id = %s
        """,
        (workspace_id,),
    )


async def get_workspace_integration_credentials(
    workspace_id: str,
    integration_type: str,
) -> dict[str, Any] | None:
    row = await fetch_one(
        """
        SELECT oauth_token, credentials_json
        FROM workspace_integrations
        WHERE workspace_id = %s AND integration_type = %s
        """,
        (workspace_id, integration_type),
    )
    if row is None:
        return None
    return _normalize_stored_credentials(
        integration_type,
        row.get("oauth_token"),
        row.get("credentials_json"),
    )


async def store_airbyte_integration_connection(
    user_id: str,
    integration_type: str,
    airbyte: dict[str, Any],
    *,
    runtime_ready: bool = False,
) -> None:
    await store_integration_credentials(
        user_id,
        integration_type,
        _build_airbyte_record_payload(airbyte, runtime_ready=runtime_ready),
        oauth_token=None,
    )


async def get_all_tokens(user_id: str) -> dict[str, str]:
    rows = await fetch_all(
        """
        SELECT integration_type, oauth_token
        FROM user_integrations
        WHERE user_id = %s AND oauth_token IS NOT NULL
        """,
        (user_id,),
    )
    return {
        row["integration_type"]: row["oauth_token"]
        for row in rows
        if row.get("oauth_token")
    }


async def get_workspace_connected_types(workspace_id: str) -> set[str]:
    rows = await fetch_all(
        """
        SELECT integration_type
        FROM workspace_integrations
        WHERE workspace_id = %s
        """,
        (workspace_id,),
    )
    return {
        row["integration_type"]
        for row in rows
        if isinstance(row.get("integration_type"), str)
    }


async def get_slack_tokens(user_id: str) -> list[dict]:
    rows = await fetch_all(
        """
        SELECT integration_type, oauth_token
        FROM user_integrations
        WHERE user_id = %s
          AND integration_type LIKE 'slack:%%'
        """,
        (user_id,),
    )
    tokens = []
    for row in rows:
        integration_type = row.get("integration_type", "")
        team_id = integration_type.split("slack:")[-1] if "slack:" in integration_type else ""
        tokens.append({"team_id": team_id, "token": row.get("oauth_token")})
    return tokens


async def create_pipeline_run(user_id: str, hypothesis: str, product_area: str) -> str:
    row = await fetch_one(
        """
        INSERT INTO pipeline_runs (user_id, hypothesis, product_area, status)
        VALUES (%s, %s, %s, 'running')
        RETURNING id
        """,
        (user_id, hypothesis, product_area),
    )
    if not row or "id" not in row:
        raise RuntimeError("Failed to create pipeline run.")
    return str(row["id"])


async def create_macroscope_run(
    workspace_id: str,
    user_id: str,
    *,
    mode: str,
    query: str,
    pipeline_run_id: str | None = None,
    chat_session_id: str | None = None,
    status: str = "queued",
) -> str:
    row = await fetch_one(
        """
        INSERT INTO macroscope_runs (
            workspace_id, user_id, pipeline_run_id, chat_session_id, mode, query, status
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        RETURNING id
        """,
        (workspace_id, user_id, pipeline_run_id, chat_session_id, mode, query, status),
    )
    if not row or "id" not in row:
        raise RuntimeError("Failed to create Macroscope run.")
    return str(row["id"])


async def set_macroscope_workflow_id(run_id: str, workflow_id: str) -> None:
    await execute(
        """
        UPDATE macroscope_runs
        SET workflow_id = %s, status = 'running'
        WHERE id = %s
        """,
        (workflow_id, run_id),
    )


async def get_macroscope_run(run_id: str) -> dict[str, Any] | None:
    return await fetch_one(
        "SELECT * FROM macroscope_runs WHERE id = %s",
        (run_id,),
    )


async def get_macroscope_run_by_workflow_id(workflow_id: str) -> dict[str, Any] | None:
    return await fetch_one(
        "SELECT * FROM macroscope_runs WHERE workflow_id = %s",
        (workflow_id,),
    )


async def complete_macroscope_run(workflow_id: str, response: str) -> None:
    await execute(
        """
        UPDATE macroscope_runs
        SET response = %s, status = 'complete', completed_at = %s
        WHERE workflow_id = %s
        """,
        (response, datetime.now(timezone.utc), workflow_id),
    )


async def fail_macroscope_run(run_id: str, error: str, *, status: str = "failed") -> None:
    await execute(
        """
        UPDATE macroscope_runs
        SET error = %s, status = %s, completed_at = %s
        WHERE id = %s
        """,
        (error, status, datetime.now(timezone.utc), run_id),
    )


async def update_pipeline_brief(run_id: str, brief: str, status: str) -> None:
    await execute(
        """
        UPDATE pipeline_runs
        SET brief = %s, status = %s, completed_at = %s
        WHERE id = %s
        """,
        (brief, status, datetime.now(timezone.utc), run_id),
    )


async def get_pipeline_run(run_id: str) -> dict:
    row = await fetch_one(
        "SELECT * FROM pipeline_runs WHERE id = %s",
        (run_id,),
    )
    if row is None:
        raise RuntimeError(f"Pipeline run {run_id} not found.")
    return row


async def get_latest_pipeline_run(user_id: str) -> dict | None:
    return await fetch_one(
        """
        SELECT *
        FROM pipeline_runs
        WHERE user_id = %s AND status = 'complete'
        ORDER BY completed_at DESC
        LIMIT 1
        """,
        (user_id,),
    )


async def create_chat_session(user_id: str, title: str | None = None) -> str:
    row = await fetch_one(
        """
        INSERT INTO chat_sessions (user_id, title)
        VALUES (%s, %s)
        RETURNING id
        """,
        (user_id, title),
    )
    if not row or "id" not in row:
        raise RuntimeError("Failed to create chat session.")
    return str(row["id"])


async def add_chat_message(
    session_id: str,
    role: str,
    content: str,
    sources_used: list[str] | None = None,
) -> None:
    await execute(
        """
        INSERT INTO chat_messages (session_id, role, content, sources_used)
        VALUES (%s, %s, %s, %s)
        """,
        (session_id, role, content, sources_used or []),
    )


async def touch_chat_session(session_id: str) -> None:
    await execute(
        """
        UPDATE chat_sessions
        SET updated_at = %s
        WHERE id = %s
        """,
        (datetime.now(timezone.utc), session_id),
    )


async def update_chat_session_title(session_id: str, title: str) -> None:
    await execute(
        "UPDATE chat_sessions SET title = %s WHERE id = %s",
        (title, session_id),
    )


async def list_chat_sessions(user_id: str, limit: int = 20) -> list[dict]:
    return await fetch_all(
        """
        SELECT id, title, created_at, updated_at
        FROM chat_sessions
        WHERE user_id = %s
        ORDER BY updated_at DESC
        LIMIT %s
        """,
        (user_id, limit),
    )


async def list_chat_messages(session_id: str, limit: int = 200) -> list[dict]:
    return await fetch_all(
        """
        SELECT id, role, content, sources_used, created_at
        FROM chat_messages
        WHERE session_id = %s
        ORDER BY created_at ASC
        LIMIT %s
        """,
        (session_id, limit),
    )


async def get_user_id_for_slack_team(team_id: str) -> str | None:
    row = await fetch_one(
        """
        SELECT user_id
        FROM user_integrations
        WHERE integration_type = %s
        """,
        (f"slack:{team_id}",),
    )
    return row.get("user_id") if row else None


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
    await execute(
        """
        INSERT INTO slack_messages (
            user_id, team_id, channel_id, slack_user_id, text, ts, thread_ts, is_dm, raw, created_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s)
        """,
        (
            user_id,
            team_id,
            channel_id,
            slack_user_id,
            text,
            ts,
            thread_ts,
            is_dm,
            _json_dumps(raw),
            datetime.now(timezone.utc),
        ),
    )


async def query_slack_messages(
    user_id: str,
    since: str | None = None,
    until: str | None = None,
    channel_id: str | None = None,
    slack_user_id: str | None = None,
    team_id: str | None = None,
    limit: int = 200,
) -> list[dict]:
    clauses = ["user_id = %s"]
    params: list[Any] = [user_id]
    if team_id:
        clauses.append("team_id = %s")
        params.append(team_id)
    if channel_id:
        clauses.append("channel_id = %s")
        params.append(channel_id)
    if slack_user_id:
        clauses.append("slack_user_id = %s")
        params.append(slack_user_id)
    if since:
        clauses.append("created_at >= %s")
        params.append(since)
    if until:
        clauses.append("created_at <= %s")
        params.append(until)
    params.append(limit)
    return await fetch_all(
        f"""
        SELECT id, team_id, channel_id, slack_user_id, text, ts, thread_ts, is_dm, created_at
        FROM slack_messages
        WHERE {' AND '.join(clauses)}
        ORDER BY created_at DESC
        LIMIT %s
        """,
        tuple(params),
    )


def _json_dumps(value: Any) -> str:
    import json

    return json.dumps(value)
