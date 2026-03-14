"""Dashboard data endpoints."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException

from db.supabase import get_all_tokens
from integrations.connections import build_linear_client

router = APIRouter(prefix="/dashboard", tags=["dashboard"])
logger = logging.getLogger(__name__)

STATUS_BUCKETS = ("backlog", "active", "blocked", "done", "other")


def _scalar_string(value: Any) -> str | None:
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    if isinstance(value, (int, float)):
        return str(value)
    return None


def _decode_tool_result(value: Any) -> Any:
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    return value


def _first_list(value: Any) -> list[dict[str, Any]]:
    decoded = _decode_tool_result(value)
    if isinstance(decoded, list):
        return [item for item in decoded if isinstance(item, dict)]
    if isinstance(decoded, dict):
        for key in (
            "nodes",
            "items",
            "issues",
            "projects",
            "cycles",
            "labels",
            "users",
            "statuses",
            "issueStatuses",
            "results",
            "data",
        ):
            candidate = decoded.get(key)
            if isinstance(candidate, list):
                return [item for item in candidate if isinstance(item, dict)]
        if all(not isinstance(v, (list, dict)) for v in decoded.values()):
            return [decoded]
    return []


def _collect_records(value: Any) -> list[dict[str, Any]]:
    decoded = _decode_tool_result(value)
    records: list[dict[str, Any]] = []
    stack = [decoded]
    while stack:
        current = stack.pop()
        if isinstance(current, list):
            stack.extend(current)
            continue
        if not isinstance(current, dict):
            continue
        title = _scalar_string(current.get("title"))
        name = _scalar_string(current.get("name"))
        identifier = _scalar_string(current.get("identifier"))
        if title or identifier:
            records.append(current)
            continue
        if name and any(
            key in current for key in ("state", "status", "assignee", "lead", "owner", "priority", "cycle")
        ):
            records.append(current)
            continue
        for value in current.values():
            if isinstance(value, (list, dict)):
                stack.append(value)
    return records or _first_list(decoded)


def _get_nested(value: dict[str, Any], *paths: str) -> Any:
    for path in paths:
        current: Any = value
        found = True
        for part in path.split("."):
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                found = False
                break
        if found and current not in (None, ""):
            return current
    return None


def _get_nested_string(value: dict[str, Any], *paths: str) -> str | None:
    return _scalar_string(_get_nested(value, *paths))


def normalize_status_bucket(status_name: str | None) -> str:
    if not status_name:
        return "other"
    lowered = status_name.strip().lower()
    if any(token in lowered for token in ("blocked", "stuck")):
        return "blocked"
    if any(token in lowered for token in ("done", "complete", "completed", "canceled", "cancelled", "closed")):
        return "done"
    if any(token in lowered for token in ("started", "in progress", "active", "in review", "review")):
        return "active"
    if any(token in lowered for token in ("backlog", "todo", "triage", "unstarted", "planned")):
        return "backlog"
    return "other"


def _issue_status_name(issue: dict[str, Any]) -> str | None:
    return _get_nested_string(
        issue,
        "state.name",
        "status.name",
        "state.type",
        "status.type",
        "state",
        "status",
    )


def _normalize_issue(issue: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": _get_nested_string(issue, "id", "identifier", "key", "title") or "",
        "identifier": _get_nested_string(issue, "identifier", "key"),
        "title": _get_nested_string(issue, "title", "name") or "Untitled issue",
        "status": _issue_status_name(issue),
        "assignee": _get_nested_string(
            issue,
            "assignee.name",
            "assignee.displayName",
            "assignee.fullName",
            "assignee.email",
        ),
        "cycle": _get_nested_string(issue, "cycle.name"),
        "labels": _get_nested(issue, "labels.nodes", "labels") or [],
    }


def build_active_issues_widget(issues: list[dict[str, Any]]) -> dict[str, Any]:
    normalized = [_normalize_issue(issue) for issue in issues]
    active_first = sorted(
        normalized,
        key=lambda issue: {
            "active": 0,
            "blocked": 1,
            "backlog": 2,
            "other": 3,
            "done": 4,
        }.get(normalize_status_bucket(issue.get("status")), 5),
    )
    visible = [issue for issue in active_first if normalize_status_bucket(issue.get("status")) != "done"][:6]
    if not visible:
        visible = active_first[:6]
    return {"items": visible}


def build_status_breakdown(issues: list[dict[str, Any]], _: list[dict[str, Any]]) -> dict[str, Any]:
    counts = {bucket: 0 for bucket in STATUS_BUCKETS}
    for issue in issues:
        counts[normalize_status_bucket(_issue_status_name(issue))] += 1
    counts["total"] = sum(counts[bucket] for bucket in STATUS_BUCKETS)
    return counts


def extract_active_cycle(cycles: list[dict[str, Any]]) -> dict[str, Any] | None:
    now = datetime.now(timezone.utc)
    normalized_cycles: list[dict[str, Any]] = []
    for cycle in cycles:
        starts_at = _get_nested(cycle, "startsAt", "startDate")
        ends_at = _get_nested(cycle, "endsAt", "endDate")
        normalized_cycles.append(
            {
                "id": _get_nested_string(cycle, "id"),
                "name": _get_nested_string(cycle, "name", "title") or "Unnamed cycle",
                "starts_at": _scalar_string(starts_at),
                "ends_at": _scalar_string(ends_at),
                "is_current": bool(_get_nested(cycle, "isCurrent", "current")),
            }
        )

    for cycle in normalized_cycles:
        if cycle["is_current"]:
            return cycle

    for cycle in normalized_cycles:
        try:
            start = (
                datetime.fromisoformat(cycle["starts_at"].replace("Z", "+00:00"))
                if cycle["starts_at"]
                else None
            )
            end = (
                datetime.fromisoformat(cycle["ends_at"].replace("Z", "+00:00"))
                if cycle["ends_at"]
                else None
            )
        except Exception:
            continue
        if start and end and start <= now <= end:
            return cycle

    return normalized_cycles[0] if normalized_cycles else None


def build_cycle_progress_widget(
    issues: list[dict[str, Any]],
    cycles: list[dict[str, Any]],
    statuses: list[dict[str, Any]],
) -> dict[str, Any]:
    counts = build_status_breakdown(issues, statuses)
    active_cycle = extract_active_cycle(cycles)
    cycle_name = active_cycle["name"] if active_cycle else None
    relevant_issues = [
        issue
        for issue in issues
        if cycle_name and _get_nested(issue, "cycle.name") == cycle_name
    ]
    scoped_counts = build_status_breakdown(relevant_issues, statuses) if relevant_issues else counts
    total = scoped_counts["total"]
    completion_pct = round((scoped_counts["done"] / total) * 100) if total else None
    return {
        "active_cycle": active_cycle,
        "counts": scoped_counts,
        "completion_pct": completion_pct,
    }


def build_projects_widget(projects: list[dict[str, Any]]) -> dict[str, Any]:
    items = []
    for project in projects[:6]:
        items.append(
            {
                "id": _get_nested_string(project, "id", "name") or "",
                "name": _get_nested_string(project, "name", "title") or "Untitled project",
                "state": _get_nested_string(project, "state", "status", "health"),
                "lead": _get_nested_string(
                    project,
                    "lead.name",
                    "owner.name",
                    "owner.displayName",
                    "creator.name",
                ),
            }
        )
    return {"items": items}


def build_top_labels(labels: list[dict[str, Any]], issues: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    counted: dict[str, int] = {}
    for label in labels:
        name = _get_nested_string(label, "name")
        if not name:
            continue
        explicit_count = _get_nested(label, "issueCount", "count")
        if isinstance(explicit_count, int):
            counted[name] = explicit_count

    if not counted and issues:
        for issue in issues:
            raw_labels = _get_nested(issue, "labels.nodes", "labels") or []
            for raw_label in raw_labels:
                if isinstance(raw_label, dict):
                    name = _get_nested_string(raw_label, "name")
                else:
                    name = _scalar_string(raw_label)
                if name:
                    counted[name] = counted.get(name, 0) + 1

    items: list[dict[str, Any]]
    if counted:
        items = [
            {"name": name, "count": count}
            for name, count in sorted(counted.items(), key=lambda item: (-item[1], item[0].lower()))[:8]
        ]
    else:
        items = [
            {"id": _get_nested_string(label, "id"), "name": _get_nested_string(label, "name")}
            for label in labels[:8]
            if _get_nested_string(label, "name")
        ]
    return {"items": items}


def build_team_load(issues: list[dict[str, Any]], users: list[dict[str, Any]]) -> dict[str, Any]:
    user_names: dict[str, str] = {}
    for user in users:
        identifier = _get_nested_string(user, "id", "email", "name") or ""
        if not identifier:
            continue
        user_names[identifier] = _get_nested_string(user, "name", "displayName", "email") or "Unknown"

    counts: dict[str, int] = {}
    unassigned_count = 0
    for issue in issues:
        bucket = normalize_status_bucket(_issue_status_name(issue))
        if bucket == "done":
            continue
        assignee_id = _get_nested_string(issue, "assignee.id", "assignee.email", "assignee.name") or ""
        assignee_name = _get_nested_string(issue, "assignee.name", "assignee.displayName", "assignee.email")
        if assignee_id:
            user_names.setdefault(assignee_id, assignee_name or "Unknown")
            counts[assignee_id] = counts.get(assignee_id, 0) + 1
        else:
            unassigned_count += 1

    items = [
        {"id": user_id, "name": user_names.get(user_id, "Unknown"), "active_issue_count": count}
        for user_id, count in sorted(counts.items(), key=lambda item: (-item[1], user_names.get(item[0], "").lower()))[:5]
    ]
    payload: dict[str, Any] = {"items": items}
    if unassigned_count:
        payload["unassigned_count"] = unassigned_count
    return payload


async def _safe_tool_call(tools_by_name: dict[str, Any], name: str, **kwargs: Any) -> tuple[Any | None, str | None]:
    tool = tools_by_name.get(name)
    if tool is None:
        return None, "Tool unavailable"
    try:
        return _decode_tool_result(await tool.arun(kwargs)), None
    except Exception as exc:
        logger.exception("Linear dashboard tool %s failed", name)
        return None, str(exc)


async def _call_with_variants(
    tools_by_name: dict[str, Any],
    name: str,
    variants: list[dict[str, Any]],
) -> tuple[Any | None, str | None]:
    last_error: str | None = None
    for kwargs in variants:
        result, error = await _safe_tool_call(tools_by_name, name, **kwargs)
        if error is None:
            return result, None
        last_error = error
    return None, last_error


def _widget_error(message: str) -> dict[str, Any]:
    return {"error": message}


@router.get("/linear/{user_id}")
async def get_linear_dashboard(user_id: str):
    try:
        tokens = await get_all_tokens(user_id)
        linear_token = tokens.get("linear")
        refreshed_at = datetime.now(timezone.utc).isoformat()
        if not linear_token:
            return {"connected": False, "refreshed_at": refreshed_at}

        client = build_linear_client(linear_token)
        tools = await client.get_tools()
        tools_by_name = {tool.name: tool for tool in tools}

        teams_result, teams_error = await _safe_tool_call(tools_by_name, "list_teams")
        team_list = _first_list(teams_result)
        primary_team = team_list[0] if team_list else {}
        team_id = _get_nested_string(primary_team, "id", "teamId")
        team_key = _get_nested_string(primary_team, "key")
        team_name = _get_nested_string(primary_team, "name")

        cycles_variants = [{"first": 5}]
        projects_variants = [{"first": 10}]
        statuses_variants = [{}]

        if team_id:
            cycles_variants.insert(0, {"teamId": team_id, "first": 5})
            projects_variants.insert(0, {"teamId": team_id, "first": 10})
            statuses_variants.insert(0, {"team": team_id})
        if team_key:
            statuses_variants.insert(0, {"team": team_key})
        if team_name:
            statuses_variants.insert(0, {"team": team_name})

        (
            issues_result,
            projects_result,
            cycles_result,
            labels_result,
            statuses_result,
            users_result,
        ) = await asyncio.gather(
            _safe_tool_call(tools_by_name, "list_issues", first=50),
            _call_with_variants(tools_by_name, "list_projects", projects_variants),
            _call_with_variants(tools_by_name, "list_cycles", cycles_variants),
            _safe_tool_call(tools_by_name, "list_issue_labels", first=30),
            _call_with_variants(tools_by_name, "list_issue_statuses", statuses_variants),
            _safe_tool_call(tools_by_name, "list_users"),
        )

        issues, issues_error = issues_result
        projects, projects_error = projects_result
        cycles, cycles_error = cycles_result
        labels, labels_error = labels_result
        statuses, statuses_error = statuses_result
        users, users_error = users_result

        issue_list = _collect_records(issues)
        project_list = _collect_records(projects)
        cycle_list = _collect_records(cycles)
        label_list = _collect_records(labels)
        status_list = _collect_records(statuses)
        user_list = _collect_records(users)

        widgets = {
            "active_issues": (
                _widget_error(issues_error) if issues_error else build_active_issues_widget(issue_list)
            ),
            "cycle_progress": (
                _widget_error(cycles_error or issues_error or statuses_error or teams_error)
                if cycles_error or issues_error or statuses_error
                else build_cycle_progress_widget(issue_list, cycle_list, status_list)
            ),
            "projects": (
                _widget_error(projects_error) if projects_error else build_projects_widget(project_list)
            ),
            "issue_status_breakdown": (
                {"counts": build_status_breakdown(issue_list, status_list), **({"error": statuses_error} if statuses_error else {})}
                if not issues_error
                else _widget_error(issues_error)
            ),
            "top_labels": (
                _widget_error(labels_error) if labels_error else build_top_labels(label_list, issue_list)
            ),
            "team_load": (
                _widget_error(users_error or issues_error)
                if users_error or issues_error
                else build_team_load(issue_list, user_list)
            ),
        }

        return {
            "connected": True,
            "refreshed_at": refreshed_at,
            "widgets": widgets,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
