"""Integration catalog and validation helpers."""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass, field
from typing import Any, Literal
from urllib.parse import urlparse


Category = Literal[
    "Product development",
    "Product analytics and insights",
    "Collaboration",
    "Product design",
    "Market intelligence",
    "Engineering Intelligence",
]
Status = Literal["supported", "blocked", "existing_non_mcp"]
AuthMode = Literal["token", "json_credentials", "oauth_future", "oauth"]
Transport = Literal["streamable_http", "stdio", "custom"]
ProviderBackend = Literal["signal_native", "airbyte_cloud"]
ConnectionMode = Literal["inline_credentials", "oauth_redirect", "external_link"]
ConnectionScope = Literal["user", "workspace"]


@dataclass(frozen=True)
class CredentialField:
    name: str
    label: str
    kind: Literal["text", "password", "url"]
    placeholder: str
    required: bool = True


@dataclass(frozen=True)
class IntegrationProvider:
    id: str
    label: str
    category: Category
    description: str
    status: Status
    surfaces: list[str]
    auth_mode: AuthMode
    transport: Transport
    credential_schema: list[CredentialField] = field(default_factory=list)
    logo_path: str | None = None
    reason_unavailable: str | None = None
    chat_enabled: bool = False
    pipeline_enabled: bool = False
    builder_key: str | None = None
    provider_backend: ProviderBackend = "signal_native"
    runtime_ready: bool = True
    connection_mode: ConnectionMode = "inline_credentials"
    connection_scope: ConnectionScope = "user"
    airbyte_provider_name: str | None = None
    connection_note: str | None = None


_PROVIDERS: tuple[IntegrationProvider, ...] = (
    IntegrationProvider(
        id="aha",
        label="Aha!",
        category="Product development",
        description="Roadmaps, ideas, and strategic planning.",
        status="supported",
        surfaces=["connect", "chat"],
        auth_mode="json_credentials",
        transport="stdio",
        credential_schema=[
            CredentialField("base_url", "Aha! URL", "url", "https://company.aha.io"),
            CredentialField("api_token", "API Token", "password", "Paste Aha! API token"),
        ],
        logo_path="/aha_logo.png",
        chat_enabled=True,
        builder_key="aha",
    ),
    IntegrationProvider(
        id="atlassian",
        label="Atlassian Jira + Confluence",
        category="Product development",
        description="Issue tracking, project status, and team documentation.",
        status="supported",
        surfaces=["connect", "chat", "pipeline"],
        auth_mode="json_credentials",
        transport="stdio",
        credential_schema=[
            CredentialField("url", "Atlassian URL", "url", "https://your-company.atlassian.net"),
            CredentialField("username", "Email", "text", "you@company.com"),
            CredentialField("api_token", "API Token", "password", "Paste Atlassian API token"),
        ],
        logo_path="/Atlassian.jpg",
        chat_enabled=True,
        pipeline_enabled=True,
        builder_key="atlassian",
    ),
    IntegrationProvider(
        id="productboard",
        label="Productboard",
        category="Product development",
        description="Feature demand, prioritization, and roadmap inputs.",
        status="supported",
        surfaces=["connect", "chat", "pipeline"],
        auth_mode="token",
        transport="stdio",
        credential_schema=[
            CredentialField("token", "API Token", "password", "Paste Productboard API token")
        ],
        logo_path="/productboard.png",
        chat_enabled=True,
        pipeline_enabled=True,
        builder_key="productboard",
    ),
    IntegrationProvider(
        id="linear",
        label="Linear",
        category="Product development",
        description="Engineering backlog, execution status, and delivery context.",
        status="supported",
        surfaces=["connect", "chat", "pipeline"],
        auth_mode="token",
        transport="custom",
        credential_schema=[
            CredentialField("token", "API Token", "password", "Paste Linear API token")
        ],
        logo_path="/linear.png",
        chat_enabled=True,
        pipeline_enabled=True,
        builder_key="linear",
        provider_backend="airbyte_cloud",
        runtime_ready=True,
        airbyte_provider_name="linear",
        connection_note="Provisioned in Airbyte Cloud. Signal chat, dashboard, and pipeline use the hosted Airbyte Linear runtime.",
    ),
    IntegrationProvider(
        id="monday",
        label="monday.com",
        category="Product development",
        description="Workflow boards, tasks, and project tracking.",
        status="supported",
        surfaces=["connect", "chat"],
        auth_mode="token",
        transport="custom",
        credential_schema=[
            CredentialField("api_token", "API Token", "password", "Paste monday.com API token")
        ],
        logo_path="/monday_logo.png",
        provider_backend="airbyte_cloud",
        runtime_ready=False,
        airbyte_provider_name="monday",
        connection_note="Provisioned in Airbyte Cloud. Signal chat and pipeline runtime still use the legacy path for now.",
    ),
    IntegrationProvider(
        id="asana",
        label="Asana",
        category="Product development",
        description="Projects, tasks, teams, and execution workflows.",
        status="supported",
        surfaces=["connect"],
        auth_mode="token",
        transport="custom",
        credential_schema=[
            CredentialField("token", "Personal Access Token", "password", "Paste Asana personal access token")
        ],
        provider_backend="airbyte_cloud",
        runtime_ready=False,
        airbyte_provider_name="asana",
        connection_note="Provisioned in Airbyte Cloud. Signal chat and pipeline runtime still use the legacy path for now.",
    ),
    IntegrationProvider(
        id="github",
        label="GitHub",
        category="Product development",
        description="Repositories, issues, pull requests, and engineering activity.",
        status="supported",
        surfaces=["connect"],
        auth_mode="token",
        transport="custom",
        credential_schema=[
            CredentialField("token", "Personal Access Token", "password", "Paste GitHub personal access token")
        ],
        provider_backend="airbyte_cloud",
        runtime_ready=False,
        airbyte_provider_name="github",
        connection_note="Provisioned in Airbyte Cloud. Signal chat and pipeline runtime still use the legacy path for now.",
    ),
    IntegrationProvider(
        id="amplitude",
        label="Amplitude",
        category="Product analytics and insights",
        description="Behavioral analytics, funnels, retention, and events.",
        status="supported",
        surfaces=["connect", "chat", "pipeline"],
        auth_mode="token",
        transport="streamable_http",
        credential_schema=[
            CredentialField("api_key", "API Key", "password", "Paste Amplitude API key")
        ],
        logo_path="/amplitude.png",
        chat_enabled=True,
        pipeline_enabled=True,
        builder_key="amplitude",
    ),
    IntegrationProvider(
        id="sentry",
        label="Sentry",
        category="Product analytics and insights",
        description="Errors, releases, events, and production issue monitoring.",
        status="supported",
        surfaces=["connect"],
        auth_mode="token",
        transport="custom",
        credential_schema=[
            CredentialField("auth_token", "Auth Token", "password", "Paste Sentry auth token")
        ],
        provider_backend="airbyte_cloud",
        runtime_ready=False,
        airbyte_provider_name="sentry",
        connection_note="Provisioned in Airbyte Cloud. Signal chat and pipeline runtime still use the legacy path for now.",
    ),
    IntegrationProvider(
        id="typeform",
        label="Typeform",
        category="Product analytics and insights",
        description="Forms, responses, workspaces, and survey feedback.",
        status="supported",
        surfaces=["connect"],
        auth_mode="token",
        transport="custom",
        credential_schema=[
            CredentialField("access_token", "Access Token", "password", "Paste Typeform personal access token")
        ],
        provider_backend="airbyte_cloud",
        runtime_ready=False,
        airbyte_provider_name="typeform",
        connection_note="Provisioned in Airbyte Cloud. Signal chat and pipeline runtime still use the legacy path for now.",
    ),
    IntegrationProvider(
        id="zendesk",
        label="Zendesk",
        category="Product analytics and insights",
        description="Support tickets, themes, pain points, and sentiment.",
        status="supported",
        surfaces=["connect", "chat", "pipeline"],
        auth_mode="token",
        transport="streamable_http",
        credential_schema=[
            CredentialField("token", "API Token", "password", "Paste Zendesk API token")
        ],
        logo_path="/zendesk.png",
        chat_enabled=True,
        pipeline_enabled=True,
        builder_key="zendesk",
    ),
    IntegrationProvider(
        id="tableau",
        label="Tableau",
        category="Product analytics and insights",
        description="Dashboards, workbooks, and business intelligence views.",
        status="supported",
        surfaces=["connect", "chat"],
        auth_mode="json_credentials",
        transport="stdio",
        credential_schema=[
            CredentialField("server_url", "Server URL", "url", "https://tableau.company.com"),
            CredentialField("site_name", "Site Name", "text", "marketing"),
            CredentialField("pat_name", "PAT Name", "text", "signal-integration"),
            CredentialField("pat_secret", "PAT Secret", "password", "Paste Tableau PAT secret"),
        ],
        logo_path="/Tableau.jpg",
        chat_enabled=True,
        builder_key="tableau",
    ),
    IntegrationProvider(
        id="slack",
        label="Slack",
        category="Collaboration",
        description="Channels, threads, and team communication.",
        status="existing_non_mcp",
        surfaces=["connect", "chat"],
        auth_mode="oauth",
        transport="custom",
        logo_path="/slack.png",
        chat_enabled=True,
    ),
    IntegrationProvider(
        id="loom",
        label="Loom",
        category="Collaboration",
        description="Async video updates and walkthroughs.",
        status="blocked",
        surfaces=["connect"],
        auth_mode="oauth_future",
        transport="custom",
        reason_unavailable="No MCP deployment path is configured for this phase.",
    ),
    IntegrationProvider(
        id="notion",
        label="Notion",
        category="Collaboration",
        description="Notes, docs, and lightweight project planning.",
        status="blocked",
        surfaces=["connect"],
        auth_mode="oauth_future",
        transport="custom",
        reason_unavailable="Deferred until the app supports OAuth-capable remote MCP connections.",
    ),
    IntegrationProvider(
        id="miro",
        label="Miro",
        category="Product design",
        description="Whiteboards, collaboration spaces, and workshops.",
        status="blocked",
        surfaces=["connect"],
        auth_mode="oauth_future",
        transport="custom",
        reason_unavailable="Deferred until the app supports OAuth-capable remote MCP connections.",
    ),
    IntegrationProvider(
        id="figma",
        label="Figma",
        category="Product design",
        description="Design files, prototypes, and handoff context.",
        status="blocked",
        surfaces=["connect"],
        auth_mode="oauth_future",
        transport="custom",
        reason_unavailable="Deferred until the app supports OAuth-capable remote MCP connections.",
    ),
    IntegrationProvider(
        id="macroscope",
        label="Macroscope",
        category="Engineering Intelligence",
        description="Code search, git history, PRs, issues, logs, and engineering delivery context.",
        status="supported",
        surfaces=["connect", "chat", "pipeline"],
        auth_mode="json_credentials",
        transport="custom",
        provider_backend="signal_native",
        runtime_ready=False,
        credential_schema=[
            CredentialField("workspace_type", "Workspace Type", "text", "github-org"),
            CredentialField("workspace_id", "Workspace ID", "text", "your-github-org"),
            CredentialField("webhook_secret", "Webhook Secret", "password", "Paste Macroscope webhook secret"),
            CredentialField("default_repo", "Default Repo", "text", "signal_machine", required=False),
        ],
        connection_mode="inline_credentials",
        connection_scope="workspace",
        connection_note="Workspace-level engineering source. Add a Macroscope webhook, allowlist Signal's callback URL, then save the workspace webhook credentials here.",
    ),
    IntegrationProvider(
        id="gong",
        label="Gong",
        category="Product analytics and insights",
        description="Customer call recordings and conversation intelligence.",
        status="blocked",
        surfaces=["connect"],
        auth_mode="oauth_future",
        transport="custom",
        reason_unavailable="No supported MCP deployment path was confirmed for this phase.",
    ),
    IntegrationProvider(
        id="surveymonkey",
        label="SurveyMonkey",
        category="Product analytics and insights",
        description="Survey responses and customer feedback analysis.",
        status="blocked",
        surfaces=["connect"],
        auth_mode="oauth_future",
        transport="custom",
        reason_unavailable="No supported MCP deployment path was confirmed for this phase.",
    ),
    IntegrationProvider(
        id="gartner",
        label="Gartner",
        category="Market intelligence",
        description="Market research and analyst reports.",
        status="blocked",
        surfaces=["connect"],
        auth_mode="oauth_future",
        transport="custom",
        reason_unavailable="No supported MCP deployment path was confirmed for this phase.",
    ),
)


_PROVIDER_MAP = {provider.id: provider for provider in _PROVIDERS}
_CATEGORY_ORDER: tuple[Category, ...] = (
    "Product development",
    "Product analytics and insights",
    "Collaboration",
    "Product design",
    "Market intelligence",
    "Engineering Intelligence",
)


def get_provider(provider_id: str) -> IntegrationProvider | None:
    return _PROVIDER_MAP.get(provider_id)


def list_providers() -> list[IntegrationProvider]:
    return list(_PROVIDERS)


def list_chat_providers() -> list[IntegrationProvider]:
    return [
        provider
        for provider in _PROVIDERS
        if provider.chat_enabled and provider.builder_key and provider.runtime_ready
    ]


def is_provider_connectable(provider: IntegrationProvider) -> bool:
    if provider.status != "supported":
        return False
    if provider.connection_mode == "external_link":
        return True
    if provider.provider_backend == "airbyte_cloud":
        return bool(
            os.getenv("AIRBYTE_CLIENT_ID")
            and os.getenv("AIRBYTE_CLIENT_SECRET")
            and os.getenv("AIRBYTE_ORGANIZATION_ID")
            and provider.airbyte_provider_name
        )
    if provider.builder_key == "aha":
        return bool(os.getenv("AHA_MCP_COMMAND") or os.getenv("AHA_MCP_SERVER_PATH"))
    if provider.builder_key == "monday":
        return bool(os.getenv("MONDAY_MCP_COMMAND") or os.getenv("MONDAY_MCP_SERVER_PATH"))
    if provider.builder_key == "tableau":
        return bool(os.getenv("TABLEAU_MCP_COMMAND") or os.getenv("TABLEAU_MCP_SERVER_PATH"))
    return True


def _provider_to_dict(provider: IntegrationProvider) -> dict[str, Any]:
    data = asdict(provider)
    data["connectable"] = is_provider_connectable(provider)
    return data


def get_catalog_payload() -> dict[str, Any]:
    groups = []
    for category in _CATEGORY_ORDER:
        providers = [
            _provider_to_dict(provider)
            for provider in _PROVIDERS
            if provider.category == category
        ]
        groups.append({"category": category, "providers": providers})
    return {"groups": groups}


def coerce_credentials(
    integration_type: str, credentials: dict[str, Any] | str | None
) -> dict[str, Any] | None:
    if credentials is None:
        return None
    if isinstance(credentials, dict):
        return credentials
    provider = get_provider(integration_type)
    if integration_type == "atlassian":
        import json

        return json.loads(credentials)
    if provider is None:
        return {"token": credentials}
    if provider.auth_mode == "token" and provider.credential_schema:
        field_name = provider.credential_schema[0].name
        return {field_name: credentials}
    return {"token": credentials}


def validate_credentials(provider: IntegrationProvider, credentials: dict[str, Any]) -> dict[str, Any]:
    cleaned: dict[str, Any] = {}
    required_fields = [field for field in provider.credential_schema if field.required]
    for field in provider.credential_schema:
        value = credentials.get(field.name)
        if value is None:
            continue
        if not isinstance(value, str):
            raise ValueError(f"{field.label} must be a string.")
        stripped = value.strip()
        if not stripped and field.required:
            raise ValueError(f"{field.label} is required.")
        if stripped:
            if field.kind == "url":
                parsed = urlparse(stripped)
                if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                    raise ValueError(f"{field.label} must be a valid http(s) URL.")
            cleaned[field.name] = stripped
    missing = [field.label for field in required_fields if not cleaned.get(field.name)]
    if missing:
        raise ValueError(f"Missing required fields: {', '.join(missing)}")
    return cleaned


def build_integration_status_map(
    connected_types: set[str],
    workspace_connected_types: set[str] | None = None,
) -> dict[str, dict[str, Any]]:
    statuses: dict[str, dict[str, Any]] = {}
    workspace_connected_types = workspace_connected_types or set()
    for provider in _PROVIDERS:
        relevant_connected_types = (
            workspace_connected_types
            if provider.connection_scope == "workspace"
            else connected_types
        )
        connected = provider.id in relevant_connected_types
        status = "connected" if connected else (
            "available" if is_provider_connectable(provider) else "not_supported_in_this_phase"
        )
        if provider.status == "blocked":
            status = "not_supported_in_this_phase"
        elif provider.status == "existing_non_mcp" and not connected:
            status = "available"
        statuses[provider.id] = {
            "connected": connected,
            "status": status,
            "label": provider.label,
            "connectable": is_provider_connectable(provider),
            "pipeline_enabled": provider.pipeline_enabled,
            "provider_backend": provider.provider_backend,
            "runtime_ready": provider.runtime_ready,
            "connection_mode": provider.connection_mode,
            "connection_scope": provider.connection_scope,
            "note": provider.connection_note,
        }
    return statuses
