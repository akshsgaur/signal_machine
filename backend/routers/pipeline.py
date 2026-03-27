"""Pipeline run endpoints + SSE streaming."""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks
from fastapi import HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from agents.pipeline import AGENT_FILE_MAP, run_signal_pipeline
from cache.store import cache
from db.supabase import create_pipeline_run, get_pipeline_run, get_latest_pipeline_run

router = APIRouter(prefix="/run", tags=["pipeline"])
ANALYSIS_CACHE_TTL_SECONDS = int(os.getenv("ANALYSIS_CACHE_TTL_SECONDS", "300"))
RUN_SOURCE_CACHE_TTL_SECONDS = int(os.getenv("RUN_SOURCE_CACHE_TTL_SECONDS", "3600"))


class RunRequest(BaseModel):
    user_id: str
    workspace_id: str | None = None
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
        request.workspace_id,
    )
    return {"run_id": run_id}


@router.get("/{run_id}/stream")
async def stream_run(run_id: str):
    """SSE: polls disk for new agent output files and emits events."""
    async def event_generator():
        base = Path(__file__).resolve().parents[1] / "storage" / "files" / run_id
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


@router.get("/{run_id}/source/{agent_key}")
async def run_source(run_id: str, agent_key: str):
    """Return one source file for a specific run so the dashboard can patch incrementally."""
    file_path = AGENT_FILE_MAP.get(agent_key)
    if not file_path:
        raise HTTPException(status_code=400, detail="Invalid agent key")

    cache_key = f"run-source:{run_id}:{agent_key}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    base = Path(__file__).resolve().parents[1] / "storage" / "files" / run_id
    disk_path = base / file_path
    if not disk_path.exists():
        return {
            "run_id": run_id,
            "agent_key": agent_key,
            "content": None,
        }

    payload = {
        "run_id": run_id,
        "agent_key": agent_key,
        "content": disk_path.read_text(encoding="utf-8"),
    }
    return cache.set(cache_key, payload, ttl_seconds=RUN_SOURCE_CACHE_TTL_SECONDS)


@router.get("/latest/{user_id}")
async def latest_run(user_id: str):
    """Return the latest completed run with per-agent outputs."""
    run = await get_latest_pipeline_run(user_id)
    if not run:
        return {"run_id": None, "status": "none", "brief": None, "sources": {}}

    run_id = str(run["id"])
    cache_key = f"latest-analysis:{user_id}:{run_id}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    base = Path(__file__).resolve().parents[1] / "storage" / "files" / run_id
    sources: dict[str, str] = {}
    for agent_key, file_path in AGENT_FILE_MAP.items():
        disk_path = base / file_path
        if disk_path.exists():
            sources[agent_key] = disk_path.read_text(encoding="utf-8")

    payload = {
        "run_id": run_id,
        "status": run["status"],
        "brief": run.get("brief"),
        "sources": sources,
    }
    return cache.set(cache_key, payload, ttl_seconds=ANALYSIS_CACHE_TTL_SECONDS)
