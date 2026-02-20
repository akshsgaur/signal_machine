"""Integration token management endpoints."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from db.supabase import get_all_tokens, store_integration_token

router = APIRouter(prefix="/integrations", tags=["integrations"])


class ConnectRequest(BaseModel):
    user_id: str
    integration_type: str
    token: str


@router.post("/connect")
async def connect_integration(request: ConnectRequest):
    """Store an API token for a user integration."""
    try:
        await store_integration_token(
            request.user_id, request.integration_type, request.token
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    return {"status": "connected", "integration": request.integration_type}


@router.get("/{user_id}")
async def list_integrations(user_id: str):
    """Return which integrations are connected for a user (no tokens exposed)."""
    try:
        tokens = await get_all_tokens(user_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    return {integration: True for integration in tokens}
