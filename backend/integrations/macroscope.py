"""Macroscope webhook integration for engineering analysis."""

from __future__ import annotations

import os
from urllib.parse import urlencode

import httpx


class MacroscopeError(RuntimeError):
    """Raised when a Macroscope webhook request fails."""


class MacroscopeClient:
    BASE_URL = "https://hooks.macroscope.com/api/v1"

    def __init__(
        self,
        *,
        workspace_type: str,
        workspace_id: str,
        webhook_secret: str,
        default_repo: str | None = None,
    ) -> None:
        self.workspace_type = workspace_type.strip()
        self.workspace_id = workspace_id.strip()
        self.webhook_secret = webhook_secret.strip()
        self.default_repo = (default_repo or "").strip() or None

    @classmethod
    def from_credentials(cls, credentials: dict[str, str]) -> "MacroscopeClient":
        workspace_type = (credentials.get("workspace_type") or "").strip()
        workspace_id = (credentials.get("workspace_id") or "").strip()
        webhook_secret = (credentials.get("webhook_secret") or "").strip()
        if not workspace_type or not workspace_id or not webhook_secret:
            raise MacroscopeError(
                "Macroscope requires workspace_type, workspace_id, and webhook_secret."
            )
        return cls(
            workspace_type=workspace_type,
            workspace_id=workspace_id,
            webhook_secret=webhook_secret,
            default_repo=credentials.get("default_repo"),
        )

    def _trigger_url(self) -> str:
        return (
            f"{self.BASE_URL}/workspaces/{self.workspace_type}/"
            f"{self.workspace_id}/query-agent-webhook-trigger"
        )

    def build_deep_analysis_query(
        self,
        *,
        request_id: str,
        hypothesis: str,
        product_area: str,
    ) -> str:
        repo_hint = (
            f"Preferred repo: {self.default_repo}\n"
            if self.default_repo
            else ""
        )
        return (
            "You are providing engineering analysis for Signal's deep product analysis.\n\n"
            f"Signal request id: {request_id}\n"
            f"Hypothesis: {hypothesis}\n"
            f"Product Area: {product_area}\n"
            f"{repo_hint}"
            "Focus on code changes, git history, PRs, issues, deployments, and other connected "
            "engineering context that materially affects this product area.\n\n"
            "Return a concise analysis with:\n"
            "1. Recent relevant changes\n"
            "2. Open engineering risks or blockers\n"
            "3. What engineering evidence supports or challenges the hypothesis\n"
            "4. The specific repos or tools you relied on"
        )

    async def trigger_query(
        self,
        *,
        query: str,
        webhook_url: str,
        timezone: str,
    ) -> str:
        payload = {
            "query": query,
            "responseDestination": {"webhookUrl": webhook_url},
            "timezone": timezone,
        }
        headers = {
            "Content-Type": "application/json",
            "X-Webhook-Secret": self.webhook_secret,
        }
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                self._trigger_url(),
                headers=headers,
                json=payload,
            )
        print(
            "[Macroscope] trigger",
            {
                "workspace_type": self.workspace_type,
                "workspace_id": self.workspace_id,
                "callback_url": webhook_url,
                "status_code": response.status_code,
            },
        )
        if response.status_code >= 400:
            print(f"[Macroscope] trigger failed body: {response.text}")
            raise MacroscopeError(
                f"Macroscope trigger failed ({response.status_code}): {response.text}"
            )
        workflow_id = (response.json() or {}).get("workflowId")
        if not isinstance(workflow_id, str) or not workflow_id.strip():
            print(f"[Macroscope] missing workflowId body: {response.text}")
            raise MacroscopeError("Macroscope did not return a workflowId.")
        print(f"[Macroscope] workflow accepted: {workflow_id.strip()}")
        return workflow_id.strip()


def build_macroscope_callback_url() -> str:
    backend_public_url = os.getenv("BACKEND_PUBLIC_URL", "").strip().rstrip("/")
    if not backend_public_url:
        raise MacroscopeError("BACKEND_PUBLIC_URL is not configured.")
    callback_url = f"{backend_public_url}/webhooks/macroscope"
    callback_token = os.getenv("MACROSCOPE_CALLBACK_TOKEN", "").strip()
    if callback_token:
        callback_url = f"{callback_url}?{urlencode({'token': callback_token})}"
    return callback_url
