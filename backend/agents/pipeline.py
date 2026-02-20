"""Signal pipeline orchestration — 2-phase parallel + sequential agent execution."""

from __future__ import annotations

import asyncio
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

from langchain.agents import create_agent
from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage

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
from mcp.connections import (
    build_amplitude_client,
    build_linear_client,
    build_productboard_client,
    build_zendesk_client,
    get_tools_for_client,
)

# ---------------------------------------------------------------------------
# Agent file destinations — also used by SSE to detect completion
# ---------------------------------------------------------------------------

AGENT_FILE_MAP: dict[str, str] = {
    "behavioral": "behavioral/amplitude_signals.md",
    "support": "support/zendesk_signals.md",
    "feature": "productboard/feature_intelligence.md",
    "execution": "linear/execution_reality.md",
}


def _print_progress(phase: str, agent: str, status: str, extra: str = "") -> None:
    ts = datetime.now().strftime("%H:%M:%S")
    icon = {"start": ">>>", "done": "<<<", "info": "---"}.get(status, "   ")
    msg = f"[{ts}] {icon} [{phase}] {agent}"
    if extra:
        msg += f" | {extra}"
    print(msg, file=sys.stderr, flush=True)


def _run_agent(
    agent,
    name: str,
    run_id: str,
    hypothesis: str,
    product_area: str,
) -> tuple[str, dict[str, str]]:
    """Run a single research agent in a ThreadPoolExecutor thread.

    Never raises — on error writes a fallback error file and returns it.
    """
    _print_progress("Phase 1", name, "start")
    t0 = time.time()
    state: dict = {
        "messages": [HumanMessage(content=f"Analyze hypothesis: {hypothesis} for product area: {product_area}")],
        "files": {},
        "run_id": run_id,
    }
    try:
        result = agent.invoke(state, config={"recursion_limit": 50})
        files = result.get("files", {}) if isinstance(result, dict) else {}
        _print_progress("Phase 1", name, "done", f"{len(files)} files, {time.time()-t0:.1f}s")
        return (name, files)
    except Exception as exc:
        _print_progress("Phase 1", name, "done", f"ERROR: {exc}")
        fallback_key = f"{name}/error.md"
        content = MISSING_SOURCE_NOTE.format(source=name) + f"\n\nError: {exc}"
        write_file_to_storage(run_id, fallback_key, content)
        return (name, {fallback_key: content})


async def run_signal_pipeline(
    run_id: str,
    user_id: str,
    hypothesis: str,
    product_area: str,
) -> None:
    """Orchestrate the full Signal 2-phase pipeline for a single run.

    Phase 1: 4 research agents run in parallel via ThreadPoolExecutor.
    Phase 2: 1 synthesis agent reads all 4 files sequentially.
    """
    try:
        # 1. Fetch all tokens from Supabase
        tokens = await get_all_tokens(user_id)

        # 2. Build MCP tools per connected integration (empty list if not connected)
        loop = asyncio.get_event_loop()

        async def _maybe_tools(builder, key: str) -> list:
            if key not in tokens:
                return []
            return await get_tools_for_client(builder(tokens[key]))

        amplitude_tools, zendesk_tools, linear_tools, productboard_tools = await asyncio.gather(
            _maybe_tools(build_amplitude_client, "amplitude"),
            _maybe_tools(build_zendesk_client, "zendesk"),
            _maybe_tools(build_linear_client, "linear"),
            _maybe_tools(build_productboard_client, "productboard"),
            return_exceptions=True,
        )
        # Collapse any exceptions to empty lists
        amplitude_tools = amplitude_tools if isinstance(amplitude_tools, list) else []
        zendesk_tools = zendesk_tools if isinstance(zendesk_tools, list) else []
        linear_tools = linear_tools if isinstance(linear_tools, list) else []
        productboard_tools = productboard_tools if isinstance(productboard_tools, list) else []

        # 3. Model + base tools
        model = init_chat_model(model="anthropic:claude-sonnet-4-6", temperature=0.0)
        base_tools = [ls, read_file, write_file, think_tool]

        def _make_agent(prompt: str, mcp_tools: list):
            return create_agent(
                model,
                tools=base_tools + mcp_tools,
                system_prompt=prompt,
                state_schema=DeepAgentState,
            )

        # 4. Create research agents
        fmt = dict(hypothesis=hypothesis, product_area=product_area)
        research_agents = {
            "behavioral": _make_agent(BEHAVIORAL_AGENT_PROMPT.format(**fmt), amplitude_tools),
            "support":    _make_agent(SUPPORT_AGENT_PROMPT.format(**fmt), zendesk_tools),
            "feature":    _make_agent(FEATURE_AGENT_PROMPT.format(**fmt), productboard_tools),
            "execution":  _make_agent(EXECUTION_AGENT_PROMPT.format(**fmt), linear_tools),
        }
        synthesis_agent = _make_agent(SYNTHESIS_AGENT_PROMPT.format(**fmt), [])

        # 5. Phase 1 — run 4 research agents in parallel
        _print_progress("Phase 1", "RESEARCH", "info", "Starting 4 research agents in parallel")
        files: dict[str, str] = {}

        with ThreadPoolExecutor(max_workers=4) as pool:
            futures = {
                pool.submit(
                    _run_agent, agent, name, run_id, hypothesis, product_area
                ): name
                for name, agent in research_agents.items()
            }
            for future in as_completed(futures):
                name, agent_files = future.result()
                files.update(agent_files)

        _print_progress("Phase 1", "RESEARCH", "done", f"{len(files)} total files")

        # 6. Phase 2 — synthesis (sequential; reads all 4 files)
        _print_progress("Phase 2", "synthesis", "start")
        t0 = time.time()
        synthesis_task = (
            "Read the 4 research files (ls first to confirm they exist) and write "
            "the decision brief to output/decision_brief.md."
        )
        synthesis_result = synthesis_agent.invoke(
            {
                "messages": [HumanMessage(content=synthesis_task)],
                "files": files,
                "run_id": run_id,
            },
            config={"recursion_limit": 50},
        )
        if isinstance(synthesis_result, dict):
            files.update(synthesis_result.get("files", {}))
        _print_progress("Phase 2", "synthesis", "done", f"{time.time()-t0:.1f}s")

        # 7. Extract brief and persist to Supabase
        brief = files.get("output/decision_brief.md", "Brief generation failed.")
        await update_pipeline_brief(run_id, brief, "complete")

    except Exception as exc:
        _print_progress("Pipeline", "ERROR", "done", str(exc))
        error_brief = f"# Pipeline Error\n\nThe pipeline failed with the following error:\n\n```\n{exc}\n```"
        write_file_to_storage(run_id, "output/error.md", error_brief)
        await update_pipeline_brief(run_id, error_brief, "failed")
