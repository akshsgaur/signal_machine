"""Reflection tool for Signal research agents."""

from langchain_core.tools import tool


@tool
def think_tool(reflection: str) -> str:
    """Reflect on findings and plan next steps.

    Call this after each MCP tool call to reason about what you found
    and what to do next before proceeding.

    Args:
        reflection: Your thoughts about the current findings and next steps.
    """
    return f"Reflection recorded: {reflection}"
