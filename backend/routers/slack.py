"""Slack OAuth integration endpoints."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import RedirectResponse

from db.supabase import get_user_id_for_slack_team, store_integration_token, store_slack_message

router = APIRouter(prefix="/slack", tags=["slack"])

SLACK_CLIENT_ID = os.getenv("SLACK_CLIENT_ID")
SLACK_CLIENT_SECRET = os.getenv("SLACK_CLIENT_SECRET")
SLACK_REDIRECT_URL = os.getenv("SLACK_REDIRECT_URL")
SLACK_SIGNING_SECRET = os.getenv("SLACK_SIGNING_SECRET")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000/connect")

PUBLIC_USER_SCOPES = [
    "channels:read",
    "channels:history",
    "users:read",
    "team:read",
]

PRIVATE_USER_SCOPES = [
    "groups:read",
    "groups:history",
    "im:read",
    "im:history",
    "mpim:read",
    "mpim:history",
    "search:read",
]


def _require_slack_env() -> None:
    if not SLACK_CLIENT_ID or not SLACK_CLIENT_SECRET or not SLACK_REDIRECT_URL:
        raise HTTPException(status_code=500, detail="Slack OAuth is not configured.")


def _verify_slack_signature(
    body: bytes, timestamp: str | None, signature: str | None
) -> bool:
    if not SLACK_SIGNING_SECRET or not timestamp or not signature:
        return False
    try:
        ts = int(timestamp)
    except ValueError:
        return False
    if abs(time.time() - ts) > 60 * 5:
        return False
    base = f"v0:{timestamp}:{body.decode('utf-8')}".encode("utf-8")
    digest = hmac.new(
        SLACK_SIGNING_SECRET.encode("utf-8"), base, hashlib.sha256
    ).hexdigest()
    expected = f"v0={digest}"
    return hmac.compare_digest(expected, signature)


@router.get("/connect")
async def connect_slack(
    user_id: str = Query(...),
    access: str = Query("public", pattern="^(public|private)$"),
):
    _require_slack_env()
    user_scopes = list(PUBLIC_USER_SCOPES)
    if access == "private":
        user_scopes += PRIVATE_USER_SCOPES

    state_payload = base64.urlsafe_b64encode(
        json.dumps({"user_id": user_id, "access": access}).encode("utf-8")
    ).decode("utf-8")

    params = {
        "client_id": SLACK_CLIENT_ID,
        "redirect_uri": SLACK_REDIRECT_URL,
        "user_scope": ",".join(user_scopes),
        "state": state_payload,
    }
    return RedirectResponse(f"https://slack.com/oauth/v2/authorize?{urlencode(params)}")


@router.get("/callback")
async def slack_callback(code: str | None = None, state: str | None = None):
    _require_slack_env()
    if not code or not state:
        raise HTTPException(status_code=400, detail="Missing code or state.")

    try:
        state_data = json.loads(base64.urlsafe_b64decode(state.encode("utf-8")))
        user_id = state_data.get("user_id")
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"Invalid state: {exc}") from exc

    if not user_id:
        raise HTTPException(status_code=400, detail="Missing user_id in state.")

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            "https://slack.com/api/oauth.v2.access",
            data={
                "client_id": SLACK_CLIENT_ID,
                "client_secret": SLACK_CLIENT_SECRET,
                "code": code,
                "redirect_uri": SLACK_REDIRECT_URL,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        data = resp.json()

    if not data.get("ok"):
        raise HTTPException(status_code=400, detail=data.get("error", "Slack error"))

    authed_user = data.get("authed_user") or {}
    token = authed_user.get("access_token")
    team = data.get("team") or {}
    team_id = team.get("id") or "unknown"

    if not token:
        raise HTTPException(status_code=400, detail="Slack token not returned.")

    await store_integration_token(user_id, f"slack:{team_id}", token)

    return RedirectResponse(f"{FRONTEND_URL}?slack=connected")


@router.post("/events")
async def slack_events(request: Request):
    if not SLACK_SIGNING_SECRET:
        raise HTTPException(status_code=500, detail="Slack signing secret missing.")

    body = await request.body()
    if not _verify_slack_signature(
        body,
        request.headers.get("x-slack-request-timestamp"),
        request.headers.get("x-slack-signature"),
    ):
        raise HTTPException(status_code=401, detail="Invalid Slack signature.")

    payload = await request.json()
    if payload.get("type") == "url_verification":
        return {"challenge": payload.get("challenge")}

    if payload.get("type") != "event_callback":
        return {"ok": True}

    event = payload.get("event") or {}
    if event.get("type") != "message":
        return {"ok": True}

    if event.get("subtype"):
        return {"ok": True}

    team_id = payload.get("team_id")
    if not team_id:
        return {"ok": True}

    user_id = await get_user_id_for_slack_team(team_id)
    if not user_id:
        return {"ok": True}

    channel_id = event.get("channel")
    slack_user_id = event.get("user")
    text = event.get("text") or ""
    ts = event.get("ts")
    thread_ts = event.get("thread_ts")
    is_dm = channel_id.startswith("D") if channel_id else False

    await store_slack_message(
        user_id=user_id,
        team_id=team_id,
        channel_id=channel_id or "",
        slack_user_id=slack_user_id or "",
        text=text,
        ts=ts or "",
        thread_ts=thread_ts,
        is_dm=is_dm,
        raw=event,
    )

    return {"ok": True}
