"""Helpers for user-visible chat activity labels and summaries."""

from __future__ import annotations

from typing import Iterable


def format_tool_activity(tool_name: str, tool_to_source: dict[str, str]) -> str:
    """Map a raw tool name to a user-friendly activity label."""
    source = tool_to_source.get(tool_name)

    exact_labels = {
        "list_issues": "Searching Linear issues",
        "list_projects": "Reviewing Linear projects",
        "list_users": "Checking team ownership",
        "jira_search": "Searching Jira backlog",
        "jira_get_issue": "Reviewing Jira issues",
        "confluence_search": "Reviewing Confluence docs",
        "confluence_get_page": "Reading Confluence pages",
        "morphik_customer_insights": "Checking customer interview excerpts",
        "morphik_get_folder": "Finding customer interview folder",
        "slack_messages": "Checking Slack conversations",
    }
    if tool_name in exact_labels:
        return exact_labels[tool_name]

    if source == "Linear":
        return "Searching Linear issues"
    if source == "Jira/Confluence":
        return "Reviewing Jira and Confluence"
    if source == "Customer Interviews (Morphik)":
        return "Reviewing customer interview excerpts"
    if source == "Slack":
        return "Checking Slack conversations"
    if source:
        return f"Checking {source}"
    return "Checking connected data"


def summarize_activity(labels: list[str], sources: Iterable[str]) -> tuple[str, int]:
    """Build the compact post-run activity summary."""
    unique_labels = list(dict.fromkeys(labels))
    unique_sources = list(dict.fromkeys(sources))
    if not unique_labels:
        return ("Thought through the request", 0)
    if len(unique_sources) == 1:
        return (f"Checked {unique_sources[0]}", len(unique_labels))
    if len(unique_sources) == 2:
        return (f"Checked {unique_sources[0]} and {unique_sources[1]}", len(unique_labels))
    return (f"Used {len(unique_labels)} tools", len(unique_labels))
