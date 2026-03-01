"""Signal pipeline orchestration — 2-phase parallel + sequential agent execution."""

from __future__ import annotations

import asyncio
import os
import sys
import time
from datetime import datetime
from typing import Callable

import httpx

from langchain.agents import create_agent
from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI
from langgraph.errors import GraphRecursionError
from mcp import McpError

from agents.file_tools import ls, read_file, write_file, write_file_to_storage
from agents.think_tool import think_tool
from agents.prompts import (
    BEHAVIORAL_AGENT_PROMPT,
    EXECUTION_AGENT_PROMPT,
    FEATURE_AGENT_PROMPT,
    MISSING_SOURCE_NOTE,
    SUPPORT_AGENT_PROMPT,
    SYNTHESIS_AGENT_PROMPT,
)
from agents.state import DeepAgentState
from db.supabase import get_all_tokens, update_pipeline_brief
from integrations.connections import (
    build_amplitude_client,
    build_linear_client,
    build_productboard_client,
    build_zendesk_client,
)

# ---------------------------------------------------------------------------
# Agent file destinations — also used by SSE to detect completion
# ---------------------------------------------------------------------------

MORPHIK_BASE_URL = os.getenv("MORPHIK_BASE_URL", "https://api.morphik.ai")
MORPHIK_API_KEY = os.getenv("MORPHIK_API_KEY")

AGENT_FILE_MAP: dict[str, str] = {
    "behavioral": "behavioral/amplitude_signals.md",
    "support": "support/zendesk_signals.md",
    "feature": "productboard/feature_intelligence.md",
    "execution": "linear/execution_reality.md",
    "insights": "insights/customer_insights.md",
}


def _print_progress(phase: str, agent: str, status: str, extra: str = "") -> None:
    ts = datetime.now().strftime("%H:%M:%S")
    icon = {"start": ">>>", "done": "<<<", "info": "---"}.get(status, "   ")
    msg = f"[{ts}] {icon} [{phase}] {agent}"
    if extra:
        msg += f" | {extra}"
    print(msg, file=sys.stderr, flush=True)


async def _run_agent(
    name: str,
    prompt: str,
    client_builder: Callable | None,
    model,
    base_tools: list,
    run_id: str,
    hypothesis: str,
    product_area: str,
) -> tuple[str, dict[str, str]]:
    """Run a single research agent as a native coroutine.

    Uses Pattern 1 (no context manager): client.get_tools() creates a short-lived
    session to enumerate tools, then each tool call creates its own fresh session.
    McpError (JSON-RPC protocol errors) is wrapped as ToolException so ToolNode
    handles it gracefully instead of crashing the agent.
    Never raises — returns a fallback file on error.
    """
    _print_progress("Phase 1", name, "start")
    t0 = time.time()
    state: dict = {
        "messages": [HumanMessage(content=f"Analyze hypothesis: {hypothesis} for product area: {product_area}")],
        "files": {},
        "run_id": run_id,
    }

    # No integration connected — write fallback immediately, skip agent run
    if client_builder is None:
        fallback_key = AGENT_FILE_MAP.get(name, f"{name}/output.md")
        content = MISSING_SOURCE_NOTE.format(source=name)
        write_file_to_storage(run_id, fallback_key, content)
        _print_progress("Phase 1", name, "done", "no integration connected")
        return (name, {fallback_key: content})

    try:
        client = client_builder()
        # Pattern 1: no context manager — each tool call creates its own
        # short-lived session, avoiding the streamable_http SSE ClosedResourceError.
        mcp_tools = await client.get_tools()
        # Enable tool-level error handling so BaseTool.arun() catches ToolException
        # (e.g. "Query too complex") and returns it as a ToolMessage instead of
        # re-raising. Without this, create_agent's ToolNode only handles
        # ToolInvocationError and lets plain ToolException escape ainvoke entirely.
        for tool in mcp_tools:
            tool.handle_tool_error = True
        agent = create_agent(
            model,
            tools=base_tools + mcp_tools,
            system_prompt=prompt,
            state_schema=DeepAgentState,
        )
        result = await agent.ainvoke(state, config={"recursion_limit": 25})
        files = result.get("files", {}) if isinstance(result, dict) else {}
        _print_progress("Phase 1", name, "done", f"{len(files)} files, {time.time()-t0:.1f}s")
        return (name, files)
    except (GraphRecursionError, McpError):
        _print_progress("Phase 1", name, "done", "no data found within tool budget")
        fallback_key = AGENT_FILE_MAP.get(name, f"{name}/output.md")
        content = MISSING_SOURCE_NOTE.format(source=name) + (
            "\n\n**Note:** The integration is connected but returned no usable data "
            "within the allowed tool call budget. This typically means the workspace "
            "has no relevant data for the queried product area."
        )
        write_file_to_storage(run_id, fallback_key, content)
        return (name, {fallback_key: content})
    except Exception as exc:
        _print_progress("Phase 1", name, "done", f"ERROR: {exc}")
        fallback_key = f"{name}/error.md"
        content = MISSING_SOURCE_NOTE.format(source=name) + f"\n\nError: {exc}"
        write_file_to_storage(run_id, fallback_key, content)
        return (name, {fallback_key: content})


async def _fetch_morphik_insights(
    user_id: str,
    run_id: str,
    hypothesis: str,
    product_area: str,
) -> tuple[str, dict[str, str]]:
    """Fetch customer insights from Morphik and write to storage. Never raises."""
    file_key = "insights/customer_insights.md"
    _print_progress("Phase 1", "insights", "start")
    t0 = time.time()

    if not MORPHIK_API_KEY:
        content = MISSING_SOURCE_NOTE.format(source="Customer Insights (Morphik)")
        write_file_to_storage(run_id, file_key, content)
        _print_progress("Phase 1", "insights", "done", "no Morphik key configured")
        return ("insights", {file_key: content})

    queries = [
        f"user feedback and pain points related to {product_area}",
        f"feature requests and product improvements for {product_area}",
        f"customer satisfaction and key themes from interviews",
    ]

    all_excerpts: list[str] = []
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            for query in queries:
                payload = {
                    "query": query,
                    "k": 5,
                    "min_score": 0.0,
                    "use_colpali": True,
                    "output_format": "text",
                    "filters": {
                        "user_id": {"$eq": user_id},
                        "source": {"$eq": "customer_interview"},
                    },
                }
                resp = await client.post(
                    f"{MORPHIK_BASE_URL}/retrieve/chunks",
                    headers={"Authorization": f"Bearer {MORPHIK_API_KEY}"},
                    json=payload,
                )
                if resp.status_code < 400:
                    for item in resp.json() or []:
                        chunk = (item.get("content") or "").strip()
                        filename = item.get("filename") or "document"
                        if chunk and len(chunk) > 20:
                            all_excerpts.append(f"**[{filename}]** {chunk[:600]}")
    except Exception as exc:
        _print_progress("Phase 1", "insights", "done", f"Morphik error: {exc}")
        content = MISSING_SOURCE_NOTE.format(source="Customer Insights (Morphik)") + f"\n\nError: {exc}"
        write_file_to_storage(run_id, file_key, content)
        return ("insights", {file_key: content})

    if not all_excerpts:
        content = (
            "# Customer Insights — Morphik\n\n"
            "No customer interview documents found. "
            "Upload interviews in the Customer Insights tab to include them in future runs."
        )
    else:
        seen: set[str] = set()
        unique = [e for e in all_excerpts if not (e in seen or seen.add(e))]  # type: ignore[func-returns-value]
        content = (
            f"# Customer Insights — Morphik Analysis\n\n"
            f"## Overview\n{len(unique)} relevant excerpts retrieved from customer interviews.\n\n"
            f"## Key Excerpts\n\n" + "\n\n---\n\n".join(unique[:12])
        )

    write_file_to_storage(run_id, file_key, content)
    _print_progress("Phase 1", "insights", "done", f"{len(all_excerpts)} excerpts, {time.time()-t0:.1f}s")
    return ("insights", {file_key: content})


async def run_signal_pipeline(
    run_id: str,
    user_id: str,
    hypothesis: str,
    product_area: str,
) -> None:
    """Orchestrate the full Signal 2-phase pipeline for a single run.

    Phase 1: 4 research agents run in parallel via asyncio.gather().
             All coroutines share the same event loop — MCP/anyio connections
             stay alive correctly without cross-thread event loop conflicts.
    Phase 2: 1 synthesis agent reads all 4 files sequentially (no MCP needed).
    """
    try:
        # 1. Fetch all tokens from Supabase
        tokens = await get_all_tokens(user_id)

        # 2. Shared model + base tools — use user-configured key/model if set
        openai_api_key = tokens.get("openai_api_key") or os.getenv("OPENAI_API_KEY")
        openai_model = tokens.get("openai_model") or "gpt-4o-mini"
        model = ChatOpenAI(model=openai_model, api_key=openai_api_key, temperature=0.0)
        base_tools = [ls, read_file, write_file, think_tool]
        fmt = dict(hypothesis=hypothesis, product_area=product_area)

        # 3. Client builders — callables that return a fresh MultiServerMCPClient.
        def _builder(build_fn, token):
            return lambda: build_fn(token)

        research_config: dict[str, tuple[Callable | None, str]] = {
            "behavioral": (
                _builder(build_amplitude_client, tokens["amplitude"]) if "amplitude" in tokens else None,
                BEHAVIORAL_AGENT_PROMPT.format(**fmt),
            ),
            "support": (
                _builder(build_zendesk_client, tokens["zendesk"]) if "zendesk" in tokens else None,
                SUPPORT_AGENT_PROMPT.format(**fmt),
            ),
            "feature": (
                _builder(build_productboard_client, tokens["productboard"]) if "productboard" in tokens else None,
                FEATURE_AGENT_PROMPT.format(**fmt),
            ),
            "execution": (
                _builder(build_linear_client, tokens["linear"]) if "linear" in tokens else None,
                EXECUTION_AGENT_PROMPT.format(**fmt),
            ),
        }

        # 4. Phase 1 — run 4 research agents in parallel via asyncio.gather()
        #    All coroutines run in the same event loop — no thread/asyncio.run() mismatch.
        _print_progress("Phase 1", "RESEARCH", "info", "Starting 4 research agents in parallel")

        results = await asyncio.gather(
            *[
                _run_agent(
                    name,
                    prompt,
                    client_builder,
                    model,
                    base_tools,
                    run_id,
                    hypothesis,
                    product_area,
                )
                for name, (client_builder, prompt) in research_config.items()
            ],
            _fetch_morphik_insights(user_id, run_id, hypothesis, product_area),
            return_exceptions=True,
        )

        files: dict[str, str] = {}
        for result in results:
            if isinstance(result, BaseException):
                _print_progress("Phase 1", "RESEARCH", "done", f"agent error: {result}")
            else:
                _, agent_files = result
                files.update(agent_files)

        _print_progress("Phase 1", "RESEARCH", "done", f"{len(files)} total files")

        # 5. Phase 2 — synthesis (sequential; reads all 4 files via virtual FS)
        _print_progress("Phase 2", "synthesis", "start")
        t0 = time.time()
        synthesis_agent = create_agent(
            model,
            tools=base_tools,
            system_prompt=SYNTHESIS_AGENT_PROMPT.format(**fmt),
            state_schema=DeepAgentState,
        )
        synthesis_result = await synthesis_agent.ainvoke(
            {
                "messages": [HumanMessage(content=(
                    "Read the 4 research files (ls first to confirm they exist) and write "
                    "the decision brief to output/decision_brief.md."
                ))],
                "files": files,
                "run_id": run_id,
            },
            config={"recursion_limit": 100},
        )
        if isinstance(synthesis_result, dict):
            files.update(synthesis_result.get("files", {}))
        _print_progress("Phase 2", "synthesis", "done", f"{time.time()-t0:.1f}s")

        # 6. Persist brief to Supabase
        brief = files.get("output/decision_brief.md", "Brief generation failed.")
        await update_pipeline_brief(run_id, brief, "complete")

    except Exception as exc:
        _print_progress("Pipeline", "ERROR", "done", str(exc))
        error_brief = f"# Pipeline Error\n\nThe pipeline failed with the following error:\n\n```\n{exc}\n```"
        write_file_to_storage(run_id, "output/error.md", error_brief)
        await update_pipeline_brief(run_id, error_brief, "failed")
