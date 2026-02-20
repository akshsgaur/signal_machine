"""State management for Signal deep agents."""

from typing import Annotated, Literal, NotRequired, TypedDict

try:
    from langchain.agents import AgentState as _AgentState
except Exception:
    class _AgentState(TypedDict, total=False):
        messages: list[dict]


class Todo(TypedDict):
    """Structured task item for planning workflows."""

    content: str
    status: Literal["pending", "in_progress", "completed"]


def file_reducer(
    left: dict[str, str] | None, right: dict[str, str] | None
) -> dict[str, str] | None:
    """Merge two file dicts; right side takes precedence."""
    if left is None:
        return right
    if right is None:
        return left
    return {**left, **right}


def todo_reducer(
    left: list[Todo] | None, right: list[Todo] | None
) -> list[Todo] | None:
    """Prefer the most recent todo list when multiple updates occur in a step."""
    if right is None:
        return left
    return right


class DeepAgentState(_AgentState):
    """Extended agent state with TODOs, virtual filesystem, and run_id."""

    todos: Annotated[NotRequired[list[Todo]], todo_reducer]
    files: Annotated[NotRequired[dict[str, str]], file_reducer]
    run_id: NotRequired[str]
