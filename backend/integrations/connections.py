"""MCP client builders for Signal integrations.

Each client is created per pipeline run — tokens are only known at runtime.
"""

from __future__ import annotations

import os
import shlex
from typing import Any

from langchain_mcp_adapters.client import MultiServerMCPClient


def _get_secret(credentials: dict[str, Any] | str, *keys: str) -> str:
    if isinstance(credentials, str):
        return credentials
    for key in keys:
        value = credentials.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    raise ValueError(f"Missing required credential field. Expected one of: {', '.join(keys)}")


def _get_value(credentials: dict[str, Any] | str, key: str) -> str:
    if isinstance(credentials, str):
        raise ValueError(f"Expected structured credentials with field {key}")
    value = credentials.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Missing required credential field: {key}")
    return value.strip()


def _stdio_server(command_env: str, path_env: str, default_command: str | None = None) -> tuple[str, list[str]]:
    command = os.getenv(command_env)
    if command:
        parts = shlex.split(command)
        return parts[0], parts[1:]
    server_path = os.getenv(path_env)
    if server_path:
        return "node", [server_path]
    if default_command:
        parts = shlex.split(default_command)
        return parts[0], parts[1:]
    raise ValueError(f"Missing MCP server configuration. Set {command_env} or {path_env}.")


def build_amplitude_client(credentials: dict[str, Any] | str) -> MultiServerMCPClient:
    """Build an Amplitude MCP client using streamable_http transport."""
    api_key = _get_secret(credentials, "api_key", "token")
    return MultiServerMCPClient(
        {
            "amplitude": {
                "transport": "streamable_http",
                "url": "https://mcp.amplitude.com/mcp",
                "headers": {"Authorization": f"Bearer {api_key}"},
            }
        }
    )


def build_zendesk_client(credentials: dict[str, Any] | str) -> MultiServerMCPClient:
    """Build a Zendesk (Swifteq) MCP client using streamable_http transport."""
    api_key = _get_secret(credentials, "token", "api_key")
    return MultiServerMCPClient(
        {
            "zendesk": {
                "transport": "streamable_http",
                "url": "https://agenthelper.swifteq.com/mcp",
                "headers": {"Authorization": f"Bearer {api_key}"},
            }
        }
    )


def build_linear_client(credentials: dict[str, Any] | str) -> MultiServerMCPClient:
    """Build a Linear MCP client using streamable_http transport."""
    api_key = _get_secret(credentials, "token", "api_key")
    return MultiServerMCPClient(
        {
            "linear": {
                "transport": "streamable_http",
                "url": "https://mcp.linear.app/mcp",
                "headers": {"Authorization": f"Bearer {api_key}"},
            }
        }
    )


def build_productboard_client(credentials: dict[str, Any] | str) -> MultiServerMCPClient:
    """Build a Productboard MCP client using stdio transport (self-hosted sidecar)."""
    token = _get_secret(credentials, "token", "api_token")
    sidecar_path = os.environ.get(
        "PRODUCTBOARD_SIDECAR_PATH", "/opt/productboard-mcp/index.js"
    )
    return MultiServerMCPClient(
        {
            "productboard": {
                "transport": "stdio",
                "command": "node",
                "args": [sidecar_path],
                "env": {"PRODUCTBOARD_TOKEN": token},
            }
        }
    )


def build_atlassian_client(credentials: dict[str, Any] | str) -> MultiServerMCPClient:
    """Build an Atlassian MCP client (Jira + Confluence) using uvx mcp-atlassian stdio transport."""
    if isinstance(credentials, str):
        import json

        creds = json.loads(credentials)
    else:
        creds = credentials
    url = _get_value(creds, "url").rstrip("/")
    username = _get_value(creds, "username")
    api_token = _get_value(creds, "api_token")
    return MultiServerMCPClient(
        {
            "atlassian": {
                "transport": "stdio",
                "command": "uvx",
                "args": ["mcp-atlassian"],
                "env": {
                    "JIRA_URL": url,
                    "JIRA_USERNAME": username,
                    "JIRA_API_TOKEN": api_token,
                    "CONFLUENCE_URL": f"{url}/wiki",
                    "CONFLUENCE_USERNAME": username,
                    "CONFLUENCE_API_TOKEN": api_token,
                },
            }
        }
    )


def build_aha_client(credentials: dict[str, Any] | str) -> MultiServerMCPClient:
    """Build an Aha! MCP client using a configured stdio server."""
    base_url = _get_value(credentials, "base_url").rstrip("/")
    api_token = _get_secret(credentials, "api_token", "token")
    command, args = _stdio_server("AHA_MCP_COMMAND", "AHA_MCP_SERVER_PATH")
    return MultiServerMCPClient(
        {
            "aha": {
                "transport": "stdio",
                "command": command,
                "args": args,
                "env": {
                    "AHA_BASE_URL": base_url,
                    "AHA_API_TOKEN": api_token,
                },
            }
        }
    )


def build_monday_client(credentials: dict[str, Any] | str) -> MultiServerMCPClient:
    """Build a monday.com MCP client using a configured stdio server."""
    api_token = _get_secret(credentials, "api_token", "token")
    command, args = _stdio_server("MONDAY_MCP_COMMAND", "MONDAY_MCP_SERVER_PATH")
    return MultiServerMCPClient(
        {
            "monday": {
                "transport": "stdio",
                "command": command,
                "args": args,
                "env": {
                    "MONDAY_API_TOKEN": api_token,
                },
            }
        }
    )


def build_tableau_client(credentials: dict[str, Any] | str) -> MultiServerMCPClient:
    """Build a Tableau MCP client using a configured stdio server."""
    command, args = _stdio_server("TABLEAU_MCP_COMMAND", "TABLEAU_MCP_SERVER_PATH")
    return MultiServerMCPClient(
        {
            "tableau": {
                "transport": "stdio",
                "command": command,
                "args": args,
                "env": {
                    "TABLEAU_SERVER_URL": _get_value(credentials, "server_url"),
                    "TABLEAU_SITE_NAME": _get_value(credentials, "site_name"),
                    "TABLEAU_PAT_NAME": _get_value(credentials, "pat_name"),
                    "TABLEAU_PAT_SECRET": _get_value(credentials, "pat_secret"),
                },
            }
        }
    )


def create_mcp_client(provider_id: str, credentials: dict[str, Any] | str) -> MultiServerMCPClient | None:
    """Build an MCP client for a supported provider."""
    builders = {
        "aha": build_aha_client,
        "amplitude": build_amplitude_client,
        "atlassian": build_atlassian_client,
        "linear": build_linear_client,
        "monday": build_monday_client,
        "productboard": build_productboard_client,
        "tableau": build_tableau_client,
        "zendesk": build_zendesk_client,
    }
    build_fn = builders.get(provider_id)
    if build_fn is None:
        return None
    return build_fn(credentials)


async def get_tools_for_client(client: MultiServerMCPClient) -> list:
    """Return tools from an MCP client, or [] on any failure."""
    try:
        return await client.get_tools()
    except Exception as exc:
        print(f"[MCP] Failed to get tools: {exc}")
        return []
