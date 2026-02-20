"""Subagent creation utilities for Signal pipeline."""

from __future__ import annotations

from langchain_core.tools import BaseTool, tool
from langchain.agents import create_agent

from agents.state import DeepAgentState


def create_subagent_agents(
    tools: list,
    subagents: list[dict],
    model,
    state_schema,
) -> tuple[dict[str, object], dict[str, BaseTool]]:
    """Compile a dict of named LangGraph agents from a subagent spec list.

    Args:
        tools: Base tool list shared across agents (unless per-agent tools specified).
        subagents: List of dicts with keys: name, prompt, description, and optional tools.
        model: LangChain chat model.
        state_schema: State TypedDict class (DeepAgentState).

    Returns:
        (agents_dict, tools_by_name)
    """
    tools_by_name: dict[str, BaseTool] = {}
    for t in tools:
        if not isinstance(t, BaseTool):
            t = tool(t)
        tools_by_name[t.name] = t

    agents: dict[str, object] = {}
    for spec in subagents:
        if "tools" in spec:
            agent_tools = [tools_by_name[name] for name in spec["tools"] if name in tools_by_name]
        else:
            agent_tools = list(tools)
        agents[spec["name"]] = create_agent(
            model,
            tools=agent_tools,
            system_prompt=spec["prompt"],
            state_schema=state_schema,
        )

    return agents, tools_by_name
