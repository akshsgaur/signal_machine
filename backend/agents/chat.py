"""Chat utilities for multi-source product intelligence."""

from __future__ import annotations

from typing import Dict, List, Tuple

import os
import httpx
from langchain_core.tools import tool

from langchain_core.messages import AIMessage, ToolMessage

from db.supabase import get_all_tokens, get_slack_tokens, query_slack_messages
from integrations.connections import (
    build_amplitude_client,
    build_atlassian_client,
    build_linear_client,
    build_productboard_client,
    build_zendesk_client,
    get_tools_for_client,
)

CHAT_SYSTEM_PROMPT = """You are Signal, a product intelligence assistant.

You answer questions using live data from the connected integrations. Use the
available tools to gather evidence. Combine signals across sources and provide
a single clear answer. If data is missing or inconclusive, say so.

If the user asks about customer interviews, feedback, or uploaded documents,
use the Morphik customer insights tool to retrieve relevant excerpts.

If a folder scope is provided, only use excerpts from that folder. If no
matching excerpts are returned, explicitly say "No matching excerpts found"
and do not invent insights.

If the user mentions a folder name (e.g., "Feb 27th", "marketing_docs"), you
must first call the Morphik folder lookup tool to resolve it, then query only
within that folder. If the folder doesn't exist, say so and stop.

Can query Jira for issues, bugs, sprint status, and project tracking (if connected).
Can query Confluence for documentation, decision records, and specs (if connected).

If the user asks about Slack, use the Slack messages tool. If they ask for
unread messages, clarify that unread status is approximated as "recent" unless
explicit read state is available. When summarizing, include channels and
people if provided.

Always include a final section titled:

Sources Used
- <Source 1>
- <Source 2>

Only list sources you actually used to form the answer.
"""

MORPHIK_BASE_URL = os.getenv("MORPHIK_BASE_URL", "https://api.morphik.ai")
MORPHIK_API_KEY = os.getenv("MORPHIK_API_KEY")


def _morphik_headers() -> dict:
    if not MORPHIK_API_KEY:
        return {}
    return {"Authorization": f"Bearer {MORPHIK_API_KEY}"}


def _normalize_folder_label(value: str) -> str:
    if not value:
        return ""
    label = value.strip().lower().lstrip("/")
    label = (
        label.replace("/", " ")
        .replace("_", " ")
        .replace("-", " ")
        .replace(".", " ")
    )
    for suffix in ("st", "nd", "rd", "th"):
        label = label.replace(suffix, "")
    months = {
        "january": "jan",
        "february": "feb",
        "march": "mar",
        "april": "apr",
        "may": "may",
        "june": "jun",
        "july": "jul",
        "august": "aug",
        "september": "sep",
        "october": "oct",
        "november": "nov",
        "december": "dec",
    }
    for full, short in months.items():
        label = label.replace(full, short)
    while "  " in label:
        label = label.replace("  ", " ")
    return label.strip()


async def resolve_folder_from_query(user_id: str, query: str) -> str | None:
    """Try to match a Morphik folder name embedded in the user query."""
    if not MORPHIK_API_KEY or not query:
        return None

    params = {"end_user_id": user_id}
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{MORPHIK_BASE_URL}/folders",
            headers=_morphik_headers(),
            params=params,
        )
        if resp.status_code >= 400:
            return None
        data = resp.json()

    if isinstance(data, list):
        folders = data
    else:
        data = data or {}
        folders = data.get("folders") or data.get("data") or data.get("items") or []
    if not folders:
        return None

    normalized_query = _normalize_folder_label(query)
    best_match = None
    best_len = 0
    for folder in folders:
        raw_name = (folder.get("name") or "").strip()
        if not raw_name:
            continue
        normalized_name = _normalize_folder_label(raw_name)
        if not normalized_name:
            continue
        if normalized_name in normalized_query:
            if len(normalized_name) > best_len:
                best_len = len(normalized_name)
                best_match = raw_name

    return best_match


def build_morphik_tool(user_id: str, folder_name: str | None):
    """Return a tool for querying Morphik customer interview documents."""

    @tool("morphik_customer_insights")
    async def morphik_customer_insights(
        query: str,
        k: int = 5,
        folder: str | None = None,
    ) -> str:
        """Search customer interview documents for relevant excerpts.

        Args:
            query: Natural-language question to search for.
            k: Max number of chunks to return.
            folder: Optional folder name to scope the search.
        """
        if not MORPHIK_API_KEY:
            return "Morphik is not configured."
        effective_folder = folder or folder_name
        filters = {
            "user_id": {"$eq": user_id},
            "source": {"$eq": "customer_interview"},
        }
        if effective_folder:
            filters["folder_name"] = {"$eq": effective_folder}
        payload = {
            "query": query,
            "k": k,
            "min_score": 0.0,
            "use_colpali": True,
            "output_format": "text",
            "filters": filters,
        }
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{MORPHIK_BASE_URL}/retrieve/chunks",
                headers=_morphik_headers(),
                json=payload,
            )
            if resp.status_code >= 400:
                return f"Morphik error: {resp.text}"
            results = resp.json() or []

            if not results and effective_folder and not effective_folder.startswith("/"):
                retry_payload = {
                    **payload,
                    "filters": {
                        **filters,
                        "folder_name": {"$eq": f"/{effective_folder}"},
                    },
                }
                retry = await client.post(
                    f"{MORPHIK_BASE_URL}/retrieve/chunks",
                    headers=_morphik_headers(),
                    json=retry_payload,
                )
                if retry.status_code < 400:
                    results = retry.json() or []

        if not results:
            return "No matching excerpts found."

        lines = []
        for item in results:
            filename = item.get("filename") or item.get("metadata", {}).get("filename")
            score = item.get("score")
            content = item.get("content") or ""
            snippet = content.strip().replace("\n", " ")
            if len(snippet) > 500:
                snippet = snippet[:500] + "..."
            score_val = f"{score:.2f}" if isinstance(score, (int, float)) else "n/a"
            lines.append(
                f"- [{filename or 'document'}] (score={score_val}): {snippet}"
            )

        return "Customer Interview Excerpts:\\n" + "\\n".join(lines)

    return morphik_customer_insights


def build_morphik_folder_tool(user_id: str):
    """Return a tool to resolve Morphik folders by name."""

    @tool("morphik_get_folder")
    async def morphik_get_folder(name: str) -> str:
        """Look up a Morphik folder by name and return its canonical name.

        Args:
            name: Folder name to look up.
        """
        if not MORPHIK_API_KEY:
            return "Morphik is not configured."
        params = {"end_user_id": user_id}
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{MORPHIK_BASE_URL}/folders",
                headers=_morphik_headers(),
                params=params,
            )
            if resp.status_code >= 400:
                return f"Morphik error: {resp.text}"
            data = resp.json() or {}

        folders = data.get("folders") or data.get("data") or data.get("items") or []
        if not folders:
            return "No folders found."

        target = name.strip().lower().lstrip("/")
        for folder in folders:
            folder_name_raw = (folder.get("name") or "").strip()
            folder_name = folder_name_raw.lower().lstrip("/")
            if folder_name == target:
                return folder_name_raw or name

        return "Folder not found."


def build_slack_tool(user_id: str):
    """Return a tool to query stored Slack messages."""

    @tool("slack_messages")
    async def slack_messages(
        query: str,
        days: int = 3,
        channel_id: str | None = None,
        slack_user_id: str | None = None,
        team_id: str | None = None,
        unread: bool = False,
    ) -> str:
        """Search stored Slack messages for relevant excerpts.

        Args:
            query: Natural-language question to search for.
            days: Lookback window in days.
            channel_id: Optional Slack channel ID.
            slack_user_id: Optional Slack user ID.
            team_id: Optional Slack workspace ID.
            unread: If true, return recent messages as a proxy for unread.
        """
        since = None
        if days and days > 0:
            from datetime import datetime, timedelta, timezone

            since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

        rows = await query_slack_messages(
            user_id=user_id,
            since=since,
            channel_id=channel_id,
            slack_user_id=slack_user_id,
            team_id=team_id,
            limit=200,
        )

        if not rows:
            tokens = await get_slack_tokens(user_id)
            token = tokens[0]["token"] if tokens else None
            if token:
                search_query = query.strip() or ""
                query_lower = search_query.lower()
                wants_dm = any(
                    term in query_lower
                    for term in ("dm", "dms", "direct message", "direct messages")
                )
                if wants_dm:
                    search_query = f"{search_query} in:im".strip()
                if unread and "is:unread" not in search_query:
                    search_query = f"{search_query} is:unread".strip()
                if unread and not search_query:
                    search_query = "is:unread"
                params = {
                    "query": search_query,
                    "sort": "timestamp",
                    "sort_dir": "desc",
                    "count": 20,
                }
                async with httpx.AsyncClient(timeout=30) as client:
                    resp = await client.get(
                        "https://slack.com/api/search.messages",
                        headers={"Authorization": f"Bearer {token}"},
                        params=params,
                    )
                    data = resp.json()
                    matches = data.get("messages", {}).get("matches") or []
                    if not matches and unread and not wants_dm:
                        # fallback: try unread across all scopes without extra query
                        params["query"] = "is:unread"
                        resp = await client.get(
                            "https://slack.com/api/search.messages",
                            headers={"Authorization": f"Bearer {token}"},
                            params=params,
                        )
                        data = resp.json()
                        matches = data.get("messages", {}).get("matches") or []
                    if not matches and unread and wants_dm:
                        params["query"] = "is:unread in:im"
                        resp = await client.get(
                            "https://slack.com/api/search.messages",
                            headers={"Authorization": f"Bearer {token}"},
                            params=params,
                        )
                        data = resp.json()
                        matches = data.get("messages", {}).get("matches") or []

                if matches:
                    lines = []
                    if unread:
                        lines.append(
                            "Note: unread state is approximated from Slack search."
                        )
                    for match in matches:
                        text = (match.get("text") or "").strip().replace("\n", " ")
                        if len(text) > 280:
                            text = text[:280] + "..."
                        channel = match.get("channel", {}).get("name") or "dm"
                        lines.append(f"- [{channel}] {text}")
                    return "Slack Messages:\\n" + "\\n".join(lines)

            return "No Slack messages found for that query."

        lines = []
        if unread:
            lines.append(
                "Note: unread state is not tracked yet; returning recent messages as a proxy."
            )

        for row in rows[:50]:
            text = (row.get("text") or "").strip().replace("\n", " ")
            if len(text) > 280:
                text = text[:280] + "..."
            lines.append(
                f"- [{row.get('created_at')}] {row.get('channel_id')}: {text}"
            )

        return "Slack Messages:\\n" + "\\n".join(lines)

    return slack_messages


async def build_chat_tools(
    user_id: str,
    folder_name: str | None = None,
) -> Tuple[List[object], Dict[str, str], List[str]]:
    """Build MCP tools from connected integrations and map tool->source."""
    tokens = await get_all_tokens(user_id)

    clients = []
    connected_sources: List[str] = []
    if "amplitude" in tokens:
        clients.append(("Amplitude", build_amplitude_client(tokens["amplitude"])))
        connected_sources.append("Amplitude")
    if "zendesk" in tokens:
        clients.append(("Zendesk", build_zendesk_client(tokens["zendesk"])))
        connected_sources.append("Zendesk")
    if "productboard" in tokens:
        clients.append(("Productboard", build_productboard_client(tokens["productboard"])))
        connected_sources.append("Productboard")
    if "linear" in tokens:
        clients.append(("Linear", build_linear_client(tokens["linear"])))
        connected_sources.append("Linear")

    tools: List[object] = []
    tool_to_source: Dict[str, str] = {}

    for source, client in clients:
        mcp_tools = await client.get_tools()
        for tool in mcp_tools:
            tool_name = getattr(tool, "name", None)
            if not tool_name:
                continue
            tool.handle_tool_error = True
            tools.append(tool)
            tool_to_source[tool_name] = source

    if "atlassian" in tokens:
        atlassian_client = build_atlassian_client(tokens["atlassian"])
        atlassian_tools = await get_tools_for_client(atlassian_client)
        for t in atlassian_tools:
            t.handle_tool_error = True
            tool_name = getattr(t, "name", None)
            if tool_name:
                tool_to_source[tool_name] = "Jira/Confluence"
        tools.extend(atlassian_tools)
        connected_sources.append("Jira/Confluence")

    if MORPHIK_API_KEY:
        folder_tool = build_morphik_folder_tool(user_id)
        if folder_tool is not None:
            tools.append(folder_tool)
            folder_name_attr = getattr(folder_tool, "name", None)
            if folder_name_attr:
                tool_to_source[folder_name_attr] = "Customer Interviews (Morphik)"

        morphik_tool = build_morphik_tool(user_id, folder_name)
        if morphik_tool is not None:
            tools.append(morphik_tool)
            morphik_name_attr = getattr(morphik_tool, "name", None)
            if morphik_name_attr:
                tool_to_source[morphik_name_attr] = "Customer Interviews (Morphik)"
        connected_sources.append("Customer Interviews (Morphik)")

    if any(key.startswith("slack:") for key in tokens):
        slack_tool = build_slack_tool(user_id)
        tools.append(slack_tool)
        slack_name = getattr(slack_tool, "name", None)
        if slack_name:
            tool_to_source[slack_name] = "Slack"
        connected_sources.append("Slack")

    return tools, tool_to_source, connected_sources


def extract_sources_used(result: object, tool_to_source: Dict[str, str]) -> List[str]:
    """Best-effort extraction of which sources were used by tool calls."""
    used = set()
    if isinstance(result, dict):
        messages = result.get("messages") or []
        for msg in messages:
            if isinstance(msg, ToolMessage):
                name = getattr(msg, "name", None) or getattr(msg, "tool", None)
                if name and name in tool_to_source:
                    used.add(tool_to_source[name])
            if isinstance(msg, AIMessage):
                tool_calls = getattr(msg, "tool_calls", None) or []
                for call in tool_calls:
                    tool_name = call.get("name")
                    if tool_name in tool_to_source:
                        used.add(tool_to_source[tool_name])
    return sorted(used)
