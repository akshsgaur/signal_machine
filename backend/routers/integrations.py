"""Integration catalog and credential management endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from db.supabase import (
    get_all_integration_credentials,
    get_all_tokens,
    store_integration_credentials,
    store_integration_token,
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
    token: str | None = None
    credentials: dict[str, Any] | None = Field(default=None)


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
        if raw_credentials is None:
            raise HTTPException(status_code=400, detail="credentials or token is required")

        cleaned = validate_credentials(provider, raw_credentials)
        await store_integration_credentials(
            request.user_id,
            request.integration_type,
            cleaned,
        )
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    return {"status": "connected", "integration": request.integration_type}


@router.get("/{user_id}")
async def list_integrations(user_id: str):
    """Return connection status for the integration catalog and legacy settings."""
    try:
        credentials = await get_all_integration_credentials(user_id)
        tokens = await get_all_tokens(user_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    connected_types = set(credentials)
    statuses = build_integration_status_map(connected_types)
    if any(key.startswith("slack:") for key in tokens):
        statuses["slack"] = {
            "connected": True,
            "status": "connected",
            "label": "Slack",
            "connectable": True,
            "pipeline_enabled": False,
        }

    for key in tokens:
        if key not in statuses:
            statuses[key] = {
                "connected": True,
                "status": "connected",
                "pipeline_enabled": False,
            }

    return statuses
