"""MCP client builders for Signal integrations.

Each client is created per pipeline run — tokens are only known at runtime.
"""

from __future__ import annotations

import os

from langchain_mcp_adapters.client import MultiServerMCPClient


def build_amplitude_client(api_key: str) -> MultiServerMCPClient:
    """Build an Amplitude MCP client using streamable_http transport."""
    return MultiServerMCPClient(
        {
            "amplitude": {
                "transport": "streamable_http",
                "url": "https://mcp.amplitude.com/mcp",
                "headers": {"Authorization": f"Bearer {api_key}"},
            }
        }
    )


def build_zendesk_client(api_key: str) -> MultiServerMCPClient:
    """Build a Zendesk (Swifteq) MCP client using streamable_http transport."""
    return MultiServerMCPClient(
        {
            "zendesk": {
                "transport": "streamable_http",
                "url": "https://agenthelper.swifteq.com/mcp",
                "headers": {"Authorization": f"Bearer {api_key}"},
            }
        }
    )


def build_linear_client(api_key: str) -> MultiServerMCPClient:
    """Build a Linear MCP client using streamable_http transport."""
    return MultiServerMCPClient(
        {
            "linear": {
                "transport": "streamable_http",
                "url": "https://mcp.linear.app/mcp",
                "headers": {"Authorization": f"Bearer {api_key}"},
            }
        }
    )


def build_productboard_client(token: str) -> MultiServerMCPClient:
    """Build a Productboard MCP client using stdio transport (self-hosted sidecar)."""
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


def build_atlassian_client(token_json: str) -> MultiServerMCPClient:
    """Build an Atlassian MCP client (Jira + Confluence) using uvx mcp-atlassian stdio transport."""
    import json
    creds = json.loads(token_json)
    url = creds["url"].rstrip("/")
    username = creds["username"]
    api_token = creds["api_token"]
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


async def get_tools_for_client(client: MultiServerMCPClient) -> list:
    """Return tools from an MCP client, or [] on any failure."""
    try:
        return await client.get_tools()
    except Exception as exc:
        print(f"[MCP] Failed to get tools: {exc}")
        return []
