"""Integration token management endpoints."""

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel

from agents.pipeline import run_signal_pipeline
from db.supabase import create_pipeline_run, get_all_tokens, store_integration_token

router = APIRouter(prefix="/integrations", tags=["integrations"])

DEFAULT_HYPOTHESIS = (
    "Provide a general PM overview of product health, customer pain, "
    "feature demand, and delivery constraints based on connected data."
)
DEFAULT_PRODUCT_AREA = "Product Overview"


class ConnectRequest(BaseModel):
    user_id: str
    integration_type: str
    token: str


@router.post("/connect")
async def connect_integration(request: ConnectRequest, background_tasks: BackgroundTasks):
    """Store an API token for a user integration."""
    try:
        await store_integration_token(
            request.user_id, request.integration_type, request.token
        )
        run_id = await create_pipeline_run(
            request.user_id, DEFAULT_HYPOTHESIS, DEFAULT_PRODUCT_AREA
        )
        background_tasks.add_task(
            run_signal_pipeline,
            run_id,
            request.user_id,
            DEFAULT_HYPOTHESIS,
            DEFAULT_PRODUCT_AREA,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    return {
        "status": "connected",
        "integration": request.integration_type,
        "run_id": run_id,
    }


@router.get("/{user_id}")
async def list_integrations(user_id: str):
    """Return which integrations are connected for a user (no tokens exposed)."""
    try:
        tokens = await get_all_tokens(user_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    connected = {integration: True for integration in tokens}
    if any(key.startswith("slack:") for key in tokens):
        connected["slack"] = True
    return connected
