"""Pipeline run endpoints + SSE streaming."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from agents.pipeline import AGENT_FILE_MAP, run_signal_pipeline
from db.supabase import create_pipeline_run, get_pipeline_run

router = APIRouter(prefix="/run", tags=["pipeline"])


class RunRequest(BaseModel):
    user_id: str
    hypothesis: str
    product_area: str


@router.post("")
async def start_run(request: RunRequest, background_tasks: BackgroundTasks):
    """Create a pipeline run and kick it off in the background."""
    run_id = await create_pipeline_run(
        request.user_id, request.hypothesis, request.product_area
    )
    background_tasks.add_task(
        run_signal_pipeline,
        run_id,
        request.user_id,
        request.hypothesis,
        request.product_area,
    )
    return {"run_id": run_id}


@router.get("/{run_id}/stream")
async def stream_run(run_id: str):
    """SSE: polls disk for new agent output files and emits events."""
    async def event_generator():
        base = Path("backend/storage/files") / run_id
        seen_agents: set[str] = set()
        brief_sent = False

        for _ in range(300):  # poll for up to 5 minutes
            await asyncio.sleep(1)

            # Check for new per-agent output files
            for agent_key, file_path in AGENT_FILE_MAP.items():
                disk_path = base / file_path
                if disk_path.exists() and agent_key not in seen_agents:
                    seen_agents.add(agent_key)
                    yield (
                        f"data: {json.dumps({'type': 'agent_update', 'agent': agent_key, 'status': 'complete'})}\n\n"
                    )

            # Check for decision brief
            brief_path = base / "output/decision_brief.md"
            if brief_path.exists() and not brief_sent:
                brief_sent = True
                content = brief_path.read_text(encoding="utf-8")
                yield (
                    f"data: {json.dumps({'type': 'brief_chunk', 'content': content})}\n\n"
                )

            # Check DB for terminal status
            try:
                run = await get_pipeline_run(run_id)
                if run["status"] in ("complete", "failed"):
                    yield (
                        f"data: {json.dumps({'type': 'status', 'status': run['status']})}\n\n"
                    )
                    break
            except Exception:
                pass

        yield f"data: {json.dumps({'type': 'status', 'status': 'timeout'})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
