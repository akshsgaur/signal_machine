"""Admin utilities for inspecting user activity."""

from __future__ import annotations

import os
from collections import defaultdict

from fastapi import APIRouter, Header, HTTPException

from db.supabase import _get_client

router = APIRouter(prefix="/admin", tags=["admin"])


def _require_admin_key(admin_key: str | None) -> None:
    expected = os.getenv("ADMIN_API_KEY")
    if not expected or admin_key != expected:
        raise HTTPException(status_code=403, detail="Forbidden")


@router.get("/users/summary")
async def users_summary(x_admin_key: str | None = Header(default=None)):
    """Return a compact summary of users, integrations, runs, and chat activity."""
    _require_admin_key(x_admin_key)

    client = _get_client()

    integrations = (
        client.table("user_integrations")
        .select("user_id,integration_type")
        .execute()
        .data
        or []
    )
    runs = (
        client.table("pipeline_runs")
        .select("user_id,status,created_at,completed_at")
        .execute()
        .data
        or []
    )
    chats = (
        client.table("chat_sessions")
        .select("user_id,created_at,updated_at")
        .execute()
        .data
        or []
    )

    summary = defaultdict(
        lambda: {
            "integrations": set(),
            "runs_total": 0,
            "runs_complete": 0,
            "runs_running": 0,
            "runs_failed": 0,
            "last_run": None,
            "chat_sessions": 0,
            "last_chat": None,
        }
    )

    for row in integrations:
        summary[row["user_id"]]["integrations"].add(row["integration_type"])

    for row in runs:
        s = summary[row["user_id"]]
        s["runs_total"] += 1
        status = row.get("status")
        if status == "complete":
            s["runs_complete"] += 1
        elif status == "running":
            s["runs_running"] += 1
        elif status == "failed":
            s["runs_failed"] += 1
        ts = row.get("completed_at") or row.get("created_at")
        if ts and (s["last_run"] is None or ts > s["last_run"]):
            s["last_run"] = ts

    for row in chats:
        s = summary[row["user_id"]]
        s["chat_sessions"] += 1
        ts = row.get("updated_at") or row.get("created_at")
        if ts and (s["last_chat"] is None or ts > s["last_chat"]):
            s["last_chat"] = ts

    return [
        {
            "user_id": user_id,
            "integrations": sorted(data["integrations"]),
            "runs_total": data["runs_total"],
            "runs_complete": data["runs_complete"],
            "runs_running": data["runs_running"],
            "runs_failed": data["runs_failed"],
            "last_run": data["last_run"],
            "chat_sessions": data["chat_sessions"],
            "last_chat": data["last_chat"],
        }
        for user_id, data in sorted(summary.items(), key=lambda x: x[0])
    ]
