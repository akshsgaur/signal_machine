"""Hosted Airbyte runtime adapters for chat, dashboard, and pipeline tools."""

from __future__ import annotations

import importlib
import os
from typing import Any

from langchain_core.tools import tool


def _extract_result_data(result: Any) -> Any:
    data = getattr(result, "data", None)
    if data is not None:
        return data
    if isinstance(result, dict):
        return result
    return result


def _normalize_linear_issue(issue: dict[str, Any]) -> dict[str, Any]:
    state = issue.get("state") or {}
    assignee = issue.get("assignee") or {}
    team = issue.get("team") or {}
    cycle = issue.get("cycle") or {}
    labels = issue.get("labels") or []
    normalized_labels = []
    for label in labels:
        if isinstance(label, dict):
            normalized_labels.append(
                {
                    "id": label.get("id"),
                    "name": label.get("name"),
                }
            )
        elif isinstance(label, str):
            normalized_labels.append({"name": label})
    return {
        "id": issue.get("id"),
        "identifier": issue.get("identifier"),
        "title": issue.get("title"),
        "description": issue.get("description"),
        "priority": issue.get("priority"),
        "state": {
            "name": state.get("name") or state.get("type"),
            "type": state.get("type"),
        },
        "assignee": {
            "id": assignee.get("id"),
            "name": assignee.get("name") or assignee.get("displayName"),
            "email": assignee.get("email"),
        },
        "team": {
            "id": team.get("id"),
            "key": team.get("key"),
            "name": team.get("name"),
        },
        "cycle": {
            "id": cycle.get("id"),
            "name": cycle.get("name"),
            "startsAt": cycle.get("startsAt") or cycle.get("startDate"),
            "endsAt": cycle.get("endsAt") or cycle.get("endDate"),
            "isCurrent": cycle.get("isCurrent") or cycle.get("current"),
        }
        if isinstance(cycle, dict) and cycle
        else None,
        "labels": {"nodes": normalized_labels},
        "project": issue.get("project"),
        "url": issue.get("url"),
        "createdAt": issue.get("createdAt"),
        "updatedAt": issue.get("updatedAt"),
    }


def _normalize_linear_project(project: dict[str, Any]) -> dict[str, Any]:
    lead = project.get("lead") or project.get("owner") or {}
    return {
        "id": project.get("id"),
        "name": project.get("name") or project.get("title"),
        "state": project.get("state") or project.get("status") or project.get("health"),
        "lead": {
            "id": lead.get("id"),
            "name": lead.get("name") or lead.get("displayName"),
        }
        if isinstance(lead, dict) and lead
        else None,
    }


def _normalize_linear_team(team: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": team.get("id"),
        "key": team.get("key"),
        "name": team.get("name"),
    }


def _normalize_linear_user(user: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": user.get("id"),
        "name": user.get("name") or user.get("displayName"),
        "email": user.get("email"),
    }


class AirbyteLinearHostedClient:
    """Expose hosted Airbyte Linear operations behind legacy-style tool names."""

    def __init__(self, external_user_id: str, connector_id: str | None = None):
        self.external_user_id = external_user_id
        self.connector_id = connector_id
        self.airbyte_client_id = os.getenv("AIRBYTE_CLIENT_ID", "").strip()
        self.airbyte_client_secret = os.getenv("AIRBYTE_CLIENT_SECRET", "").strip()
        self.organization_id = os.getenv("AIRBYTE_ORGANIZATION_ID", "").strip()
        if not self.airbyte_client_id or not self.airbyte_client_secret:
            raise ValueError("AIRBYTE_CLIENT_ID and AIRBYTE_CLIENT_SECRET are required.")
        self._connector: Any | None = None

    async def _get_connector(self) -> Any:
        if self._connector is not None:
            return self._connector

        module = importlib.import_module("airbyte_agent_linear")
        connector_cls = getattr(module, "LinearConnector")

        try:
            self._connector = connector_cls(
                external_user_id=self.external_user_id,
                airbyte_client_id=self.airbyte_client_id,
                airbyte_client_secret=self.airbyte_client_secret,
            )
            return self._connector
        except TypeError:
            pass

        package_module = importlib.import_module("airbyte_agent_linear")
        auth_cls = getattr(package_module, "AirbyteAuthConfig")
        auth_errors: list[str] = []
        for kwargs in (
            {
                "connector_id": self.connector_id,
                "organization_id": self.organization_id,
                "airbyte_client_id": self.airbyte_client_id,
                "airbyte_client_secret": self.airbyte_client_secret,
            },
            {
                "customer_name": self.external_user_id,
                "organization_id": self.organization_id,
                "airbyte_client_id": self.airbyte_client_id,
                "airbyte_client_secret": self.airbyte_client_secret,
            },
            {
                "external_user_id": self.external_user_id,
                "organization_id": self.organization_id,
                "airbyte_client_id": self.airbyte_client_id,
                "airbyte_client_secret": self.airbyte_client_secret,
            },
        ):
            try:
                auth_config = auth_cls(**{k: v for k, v in kwargs.items() if v})
                self._connector = connector_cls(auth_config=auth_config)
                return self._connector
            except TypeError as exc:
                auth_errors.append(str(exc))

        raise RuntimeError(
            "Unable to initialize hosted Airbyte Linear connector. "
            f"Auth config attempts failed: {' | '.join(auth_errors)}"
        )

    async def _execute(self, entity: str, action: str, params: dict[str, Any] | None = None) -> Any:
        connector = await self._get_connector()
        return await connector.execute(entity, action, params or {})

    async def get_tools(self) -> list[Any]:
        @tool("list_issues")
        async def list_issues(first: int = 25) -> list[dict[str, Any]]:
            """List recent Linear issues."""
            result = await self._execute("issues", "list", {"limit": first})
            data = _extract_result_data(result) or []
            if not isinstance(data, list):
                return []
            return [_normalize_linear_issue(item) for item in data if isinstance(item, dict)]

        @tool("list_projects")
        async def list_projects(first: int = 10, teamId: str | None = None) -> list[dict[str, Any]]:
            """List Linear projects."""
            params: dict[str, Any] = {"limit": first}
            if teamId:
                params["team_id"] = teamId
            result = await self._execute("projects", "list", params)
            data = _extract_result_data(result) or []
            if not isinstance(data, list):
                return []
            return [_normalize_linear_project(item) for item in data if isinstance(item, dict)]

        @tool("list_teams")
        async def list_teams() -> list[dict[str, Any]]:
            """List Linear teams."""
            result = await self._execute("teams", "list", {"limit": 20})
            data = _extract_result_data(result) or []
            if not isinstance(data, list):
                return []
            return [_normalize_linear_team(item) for item in data if isinstance(item, dict)]

        @tool("list_users")
        async def list_users() -> list[dict[str, Any]]:
            """List Linear users."""
            result = await self._execute("users", "list", {"limit": 50})
            data = _extract_result_data(result) or []
            if not isinstance(data, list):
                return []
            return [_normalize_linear_user(item) for item in data if isinstance(item, dict)]

        @tool("list_issue_labels")
        async def list_issue_labels(first: int = 50) -> list[dict[str, Any]]:
            """Derive Linear issue labels from recent issues."""
            result = await self._execute("issues", "list", {"limit": first})
            data = _extract_result_data(result) or []
            labels_by_name: dict[str, dict[str, Any]] = {}
            for item in data if isinstance(data, list) else []:
                if not isinstance(item, dict):
                    continue
                labels = item.get("labels") or []
                for label in labels:
                    if isinstance(label, dict):
                        name = label.get("name")
                        if isinstance(name, str) and name.strip():
                            labels_by_name[name.strip()] = {
                                "id": label.get("id"),
                                "name": name.strip(),
                            }
                    elif isinstance(label, str) and label.strip():
                        labels_by_name[label.strip()] = {"name": label.strip()}
            return list(labels_by_name.values())

        @tool("list_issue_statuses")
        async def list_issue_statuses(team: str | None = None) -> list[dict[str, Any]]:
            """Derive issue statuses from recent issues."""
            result = await self._execute("issues", "list", {"limit": 100})
            data = _extract_result_data(result) or []
            statuses_by_name: dict[str, dict[str, Any]] = {}
            for item in data if isinstance(data, list) else []:
                if not isinstance(item, dict):
                    continue
                issue_team = item.get("team") or {}
                if team:
                    team_candidates = {
                        str(issue_team.get("id") or ""),
                        str(issue_team.get("key") or ""),
                        str(issue_team.get("name") or ""),
                    }
                    if team not in team_candidates:
                        continue
                state = item.get("state") or {}
                name = state.get("name") or state.get("type")
                if isinstance(name, str) and name.strip():
                    statuses_by_name[name.strip()] = {
                        "name": name.strip(),
                        "type": state.get("type"),
                    }
            return list(statuses_by_name.values())

        for tool_fn in (list_issues, list_projects, list_teams, list_users, list_issue_labels, list_issue_statuses):
            tool_fn.handle_tool_error = True
        return [list_issues, list_projects, list_teams, list_users, list_issue_labels, list_issue_statuses]
