"""TODO management tools for Signal agent task tracking."""

from typing import Annotated

from langchain_core.messages import ToolMessage
from langchain_core.tools import InjectedToolCallId, tool
from langgraph.prebuilt.tool_node import InjectedState
from langgraph.types import Command

from agents.state import DeepAgentState, Todo


_WRITE_TODOS_DESCRIPTION = """Create or update the agent's TODO list for task planning and tracking.

Parameters:
- todos: List of Todo items with content and status fields
  - content: Short description of the task
  - status: 'pending', 'in_progress', or 'completed'

Best practices:
- Keep 3-8 tasks total
- Only one task in_progress at a time
- Always send the full updated list when making changes"""


@tool(description=_WRITE_TODOS_DESCRIPTION, parse_docstring=True)
def write_todos(
    todos: list[Todo],
    tool_call_id: Annotated[str, InjectedToolCallId],
) -> Command:
    """Create or update the agent's TODO list.

    Args:
        todos: List of Todo items with content and status
        tool_call_id: Tool call identifier for message response
    """
    return Command(
        update={
            "todos": todos,
            "messages": [ToolMessage("Updated todo list.", tool_call_id=tool_call_id)],
        }
    )


@tool(parse_docstring=True)
def read_todos(
    state: Annotated[DeepAgentState, InjectedState],
    tool_call_id: Annotated[str, InjectedToolCallId],
) -> str:
    """Read the current TODO list from agent state.

    Args:
        state: Injected agent state containing the current TODO list
        tool_call_id: Injected tool call identifier for message tracking
    """
    todos = state.get("todos", [])
    if not todos:
        return "No todos currently in the list."

    result = "Current TODO List:\n"
    for i, todo in enumerate(todos, 1):
        result += f"{i}. [{todo['status']}] {todo['content']}\n"

    return result.strip()
