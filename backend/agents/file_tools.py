"""Virtual filesystem tools for Signal agent state management."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Annotated

from langchain_core.messages import ToolMessage
from langchain_core.tools import InjectedToolCallId, tool
from langgraph.prebuilt.tool_node import InjectedState
from langgraph.types import Command

from agents.state import DeepAgentState


_LS_DESCRIPTION = """List all files in the virtual filesystem stored in agent state.

Shows what files currently exist in agent memory. Use this to orient yourself before
other file operations and maintain awareness of your file organization.

No parameters required — simply call ls() to see all available files."""

_READ_FILE_DESCRIPTION = """Read content from a file in the virtual filesystem with optional pagination.

Returns file content with line numbers and supports reading large files in chunks.

Parameters:
- file_path (required): Path to the file you want to read
- offset (optional, default=0): Line number to start reading from
- limit (optional, default=2000): Maximum number of lines to read"""

_WRITE_FILE_DESCRIPTION = """Create a new file or completely overwrite an existing file in the virtual filesystem.

Files are stored in agent state and mirrored to disk at backend/storage/files/{run_id}/.

Parameters:
- file_path (required): Path where the file should be created/overwritten
- content (required): The complete content to write to the file"""


def _storage_root() -> Path:
    override = os.getenv("FILES_STORAGE_ROOT")
    if override:
        return Path(override)
    return Path(__file__).resolve().parents[1] / "storage" / "files"


def _safe_path(base: Path, file_path: str) -> Path:
    safe = (base / file_path).resolve()
    if not str(safe).startswith(str(base.resolve())):
        raise ValueError("Invalid file_path: path traversal outside storage root")
    return safe


@tool(description=_LS_DESCRIPTION)
def ls(state: Annotated[DeepAgentState, InjectedState]) -> list[str]:
    """List all files in the virtual filesystem."""
    return sorted(state.get("files", {}).keys())


@tool(description=_READ_FILE_DESCRIPTION)
def read_file(
    file_path: str,
    state: Annotated[DeepAgentState, InjectedState],
    offset: int = 0,
    limit: int = 2000,
) -> str:
    """Read file content from virtual filesystem with optional offset and limit."""
    files = state.get("files", {})
    if file_path not in files:
        return f"Error: File '{file_path}' not found"

    content = files[file_path]
    if not content:
        return "System reminder: File exists but has empty contents"

    lines = content.splitlines()
    start_idx = offset
    end_idx = min(start_idx + limit, len(lines))

    if start_idx >= len(lines):
        return f"Error: Line offset {offset} exceeds file length ({len(lines)} lines)"

    result_lines = []
    for i in range(start_idx, end_idx):
        result_lines.append(f"{i + 1:6d}\t{lines[i][:2000]}")

    return "\n".join(result_lines)


@tool(description=_WRITE_FILE_DESCRIPTION)
def write_file(
    file_path: str,
    content: str,
    state: Annotated[DeepAgentState, InjectedState],
    tool_call_id: Annotated[str, InjectedToolCallId],
) -> Command:
    """Write content to a file in the virtual filesystem and mirror to disk."""
    files = dict(state.get("files", {}))
    files[file_path] = content

    run_id = state.get("run_id") or "default"
    write_file_to_storage(run_id, file_path, content)

    return Command(
        update={
            "files": files,
            "messages": [ToolMessage(f"Updated file {file_path}", tool_call_id=tool_call_id)],
        }
    )


def write_file_to_storage(run_id: str, file_path: str, content: str) -> None:
    """Write content to storage/files/{run_id}/{file_path} on disk."""
    base = _storage_root() / run_id
    disk_path = _safe_path(base, file_path)
    disk_path.parent.mkdir(parents=True, exist_ok=True)
    disk_path.write_text(content, encoding="utf-8")
