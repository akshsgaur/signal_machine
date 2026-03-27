"""Macroscope webhook endpoints."""

from __future__ import annotations

import os

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from agents.chat_session_streams import publish as publish_chat_session_event
from db.supabase import (
    add_chat_message,
    complete_macroscope_run,
    get_macroscope_run_by_workflow_id,
    touch_chat_session,
)

router = APIRouter(prefix="/webhooks/macroscope", tags=["macroscope"])


class MacroscopeCallbackPayload(BaseModel):
    query: str
    response: str
    workflowId: str


@router.post("")
async def macroscope_callback(
    payload: MacroscopeCallbackPayload,
    token: str | None = Query(default=None),
):
    expected_token = os.getenv("MACROSCOPE_CALLBACK_TOKEN", "").strip()
    if expected_token and token != expected_token:
        raise HTTPException(status_code=401, detail="Invalid callback token.")

    run = await get_macroscope_run_by_workflow_id(payload.workflowId)
    if run is None:
        raise HTTPException(status_code=404, detail="Unknown Macroscope workflow.")

    print(
        f"[Macroscope callback] workflow_id={payload.workflowId} mode={run.get('mode')}"
    )
    await complete_macroscope_run(payload.workflowId, payload.response.strip())
    if run.get("mode") == "chat" and run.get("chat_session_id"):
        session_id = str(run["chat_session_id"])
        message_text = payload.response.strip()
        sources_used = ["Macroscope"]
        await add_chat_message(session_id, "assistant", message_text, sources_used)
        await touch_chat_session(session_id)
        await publish_chat_session_event(
            session_id,
            {
                "type": "final_response",
                "message": message_text,
                "sources_used": sources_used,
                "origin": "macroscope",
            },
        )
    return {"status": "ok"}
