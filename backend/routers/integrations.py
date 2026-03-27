"""Integration catalog and credential management endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from db.supabase import (
    get_all_integration_credentials,
    get_all_tokens,
    get_workspace_connected_types,
    list_integration_records,
    list_workspace_integration_records,
    store_airbyte_integration_connection,
    store_integration_credentials,
    store_integration_token,
    store_workspace_integration_credentials,
)
from integrations.airbyte import (
    AirbyteClient,
    AirbyteError,
    build_airbyte_credentials,
)
from integrations.registry import (
    build_integration_status_map,
    coerce_credentials,
    get_catalog_payload,
    get_provider,
    is_provider_connectable,
    validate_credentials,
)

router = APIRouter(prefix="/integrations", tags=["integrations"])

SPECIAL_TOKEN_KEYS = {"openai_api_key", "openai_model"}


class ConnectRequest(BaseModel):
    user_id: str
    integration_type: str
    workspace_id: str | None = None
    token: str | None = None
    credentials: dict[str, Any] | None = Field(default=None)


class OAuthStartRequest(BaseModel):
    user_id: str
    redirect_url: str


def _build_airbyte_connection_name(user_id: str, provider_label: str) -> str:
    slug = provider_label.lower().replace(" ", "-").replace(".", "").replace("!", "")
    return f"{slug}-{user_id[:12]}"


def _resolve_workspace_id(user_id: str, workspace_id: str | None) -> str:
    return (workspace_id or user_id).strip()


@router.get("/catalog")
async def get_catalog():
    """Return the frontend integration catalog grouped by category."""
    return get_catalog_payload()


@router.post("/connect")
async def connect_integration(request: ConnectRequest):
    """Store credentials for a user integration."""
    try:
        if request.integration_type in SPECIAL_TOKEN_KEYS:
            if not request.token:
                raise HTTPException(status_code=400, detail="token is required")
            await store_integration_token(
                request.user_id,
                request.integration_type,
                request.token.strip(),
            )
            return {"status": "connected", "integration": request.integration_type}

        provider = get_provider(request.integration_type)
        if provider is None:
            raise HTTPException(status_code=404, detail="Unknown integration")
        workspace_id = _resolve_workspace_id(request.user_id, request.workspace_id)
        if provider.status != "supported":
            raise HTTPException(
                status_code=400,
                detail=provider.reason_unavailable or "This integration is not supported in this phase.",
            )
        if not is_provider_connectable(provider):
            raise HTTPException(
                status_code=400,
                detail="This integration is not deployable in the current environment yet.",
            )

        raw_credentials = request.credentials
        if raw_credentials is None and request.token is not None:
            raw_credentials = coerce_credentials(request.integration_type, request.token)
        if raw_credentials is None and provider.connection_mode == "external_link":
            raw_credentials = {"connected_via": "external_link", "configured_by": request.user_id}
        if raw_credentials is None:
            raise HTTPException(status_code=400, detail="credentials or token is required")

        cleaned = validate_credentials(provider, raw_credentials)
        if provider.connection_scope == "workspace":
            await store_workspace_integration_credentials(
                workspace_id,
                request.integration_type,
                cleaned,
                oauth_token=request.token.strip() if request.token else None,
            )
            return {
                "status": "connected",
                "integration": request.integration_type,
                "connection_scope": provider.connection_scope,
                "workspace_id": workspace_id,
            }
        if provider.provider_backend == "airbyte_cloud":
            connector = await AirbyteClient.from_env().get_or_create_connector(
                provider_id=provider.id,
                external_user_id=request.user_id,
                workspace_name=request.user_id,
                name=_build_airbyte_connection_name(request.user_id, provider.label),
                credentials=build_airbyte_credentials(provider.id, cleaned),
            )
            await store_airbyte_integration_connection(
                request.user_id,
                request.integration_type,
                {
                    "provider_name": provider.airbyte_provider_name,
                    "connector_id": connector.get("connectorId") or connector.get("id"),
                    "workspace_name": request.user_id,
                    "status": connector.get("status") or "active",
                    "name": connector.get("name"),
                    "organization_id": AirbyteClient.from_env().organization_id,
                },
                runtime_ready=provider.runtime_ready,
            )
            return {
                "status": "connected",
                "integration": request.integration_type,
                "provider_backend": provider.provider_backend,
                "runtime_ready": provider.runtime_ready,
            }
        await store_integration_credentials(
            request.user_id,
            request.integration_type,
            cleaned,
        )
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except AirbyteError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    return {"status": "connected", "integration": request.integration_type}


@router.post("/connect/{provider_id}/oauth/start")
async def start_provider_oauth(provider_id: str, request: OAuthStartRequest):
    """Initiate a server-side Airbyte OAuth flow for a provider."""
    provider = get_provider(provider_id)
    if provider is None:
        raise HTTPException(status_code=404, detail="Unknown integration")
    if provider.provider_backend != "airbyte_cloud":
        raise HTTPException(status_code=400, detail="OAuth start is only supported for Airbyte-backed providers.")
    if provider.connection_mode != "oauth_redirect":
        raise HTTPException(status_code=400, detail="This provider does not use OAuth connect flow yet.")
    try:
        payload = await AirbyteClient.from_env().initiate_oauth(
            provider_id=provider.id,
            external_user_id=request.user_id,
            redirect_url=request.redirect_url,
        )
    except AirbyteError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    return payload


@router.get("/{user_id}")
async def list_integrations(user_id: str, workspace_id: str | None = None):
    """Return connection status for the integration catalog and legacy settings."""
    try:
        resolved_workspace_id = _resolve_workspace_id(user_id, workspace_id)
        credentials = await get_all_integration_credentials(user_id)
        records = await list_integration_records(user_id)
        tokens = await get_all_tokens(user_id)
        workspace_records = await list_workspace_integration_records(resolved_workspace_id)
        workspace_connected_types = await get_workspace_connected_types(resolved_workspace_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    connected_types = set(credentials)
    statuses = build_integration_status_map(connected_types, workspace_connected_types)
    for row in records:
        integration_type = row.get("integration_type")
        if not isinstance(integration_type, str):
            continue
        metadata = row.get("credentials_json")
        if isinstance(metadata, dict) and metadata.get("_provider_backend") == "airbyte_cloud":
            airbyte = metadata.get("_airbyte") or {}
            provider = get_provider(integration_type)
            runtime_ready = bool(metadata.get("_runtime_ready")) or bool(
                provider and provider.runtime_ready
            )
            statuses[integration_type] = {
                **statuses.get(integration_type, {}),
                "connected": True,
                "status": "connected",
                "provider_backend": "airbyte_cloud",
                "runtime_ready": runtime_ready,
                "airbyte_status": airbyte.get("status"),
                "airbyte_connector_id": airbyte.get("connector_id"),
                "connected_at": row.get("connected_at"),
                "updated_at": row.get("updated_at"),
            }
    for row in workspace_records:
        integration_type = row.get("integration_type")
        if not isinstance(integration_type, str):
            continue
        statuses[integration_type] = {
            **statuses.get(integration_type, {}),
            "connected": True,
            "status": "connected",
            "connection_scope": "workspace",
            "connected_at": row.get("connected_at"),
            "updated_at": row.get("updated_at"),
        }
    if any(key.startswith("slack:") for key in tokens):
        statuses["slack"] = {
            "connected": True,
            "status": "connected",
            "label": "Slack",
            "connectable": True,
            "pipeline_enabled": False,
            "provider_backend": "signal_native",
            "runtime_ready": True,
            "connection_scope": "user",
        }

    for key in tokens:
        if key not in statuses:
            statuses[key] = {
                "connected": True,
                "status": "connected",
                "pipeline_enabled": False,
                "provider_backend": "signal_native",
                "runtime_ready": True,
                "connection_scope": "user",
            }

    return statuses
