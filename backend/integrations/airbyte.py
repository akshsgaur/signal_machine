"""Airbyte Agent Engine helpers for Signal integrations."""

from __future__ import annotations

import os
from typing import Any

import httpx


AIRBYTE_API_BASE = os.getenv("AIRBYTE_API_BASE", "https://api.airbyte.ai/api/v1").rstrip("/")

AIRBYTE_CONNECTOR_DEFINITION_IDS: dict[str, str] = {
    "asana": "d0243522-dccf-4978-8ba0-37ed47a0bdbf",
    "github": "ef69ef6e-aa7f-4af1-a01d-ef775033524e",
    "linear": "1c5d8316-ed42-4473-8fbc-2626f03f070c",
    "monday": "80a54ea2-9959-4040-aac1-eee42423ec9b",
    "sentry": "cdaf146a-9b75-49fd-9dd2-9d64a0bb4781",
    "typeform": "e7eff203-90bf-43e5-a240-19ea3056c474",
}


class AirbyteError(RuntimeError):
    """Raised when an Airbyte API request fails."""


def is_airbyte_enabled() -> bool:
    return bool(
        os.getenv("AIRBYTE_CLIENT_ID")
        and os.getenv("AIRBYTE_CLIENT_SECRET")
        and os.getenv("AIRBYTE_ORGANIZATION_ID")
    )


def get_airbyte_definition_id(provider_id: str) -> str | None:
    return AIRBYTE_CONNECTOR_DEFINITION_IDS.get(provider_id)


def build_airbyte_credentials(provider_id: str, credentials: dict[str, Any]) -> dict[str, Any]:
    """Map Signal credential fields to Airbyte connector auth fields."""
    if provider_id == "linear":
        token = str(credentials.get("token", "")).strip()
        if not token:
            raise ValueError("Linear API Token is required.")
        return {"api_key": token}
    if provider_id == "monday":
        token = str(credentials.get("api_token", "")).strip()
        if not token:
            raise ValueError("monday.com API Token is required.")
        return {"api_key": token}
    if provider_id == "asana":
        token = str(credentials.get("token", "")).strip()
        if not token:
            raise ValueError("Asana Personal Access Token is required.")
        return {"token": token}
    if provider_id == "github":
        token = str(credentials.get("token", "")).strip()
        if not token:
            raise ValueError("GitHub Personal Access Token is required.")
        return {"token": token}
    if provider_id == "sentry":
        token = str(credentials.get("auth_token", "")).strip()
        if not token:
            raise ValueError("Sentry Auth Token is required.")
        return {"auth_token": token}
    if provider_id == "typeform":
        token = str(credentials.get("access_token", "")).strip()
        if not token:
            raise ValueError("Typeform Access Token is required.")
        return {"access_token": token}
    raise ValueError(f"{provider_id} is not configured for Airbyte-backed connect flow.")


def _extract_error_message(payload: Any) -> str:
    if isinstance(payload, dict):
        for key in ("message", "detail", "error", "title"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return ""


class AirbyteClient:
    """Minimal Agent Engine client for Signal's connect lifecycle."""

    ORGANIZATION_HEADER = "X-Organization-Id"

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        organization_id: str,
        *,
        api_base: str = AIRBYTE_API_BASE,
        timeout: float = 30.0,
    ) -> None:
        self.client_id = client_id
        self.client_secret = client_secret
        self.organization_id = organization_id
        self.api_base = api_base.rstrip("/")
        self.timeout = timeout

    @classmethod
    def from_env(cls) -> "AirbyteClient":
        client_id = os.getenv("AIRBYTE_CLIENT_ID", "").strip()
        client_secret = os.getenv("AIRBYTE_CLIENT_SECRET", "").strip()
        organization_id = os.getenv("AIRBYTE_ORGANIZATION_ID", "").strip()
        if not client_id or not client_secret or not organization_id:
            raise AirbyteError(
                "Airbyte Agent Engine is not configured. Set AIRBYTE_CLIENT_ID, "
                "AIRBYTE_CLIENT_SECRET, and AIRBYTE_ORGANIZATION_ID."
            )
        return cls(client_id, client_secret, organization_id)

    def _headers(self, *, bearer_token: str | None = None) -> dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            self.ORGANIZATION_HEADER: self.organization_id,
        }
        if bearer_token:
            headers["Authorization"] = f"Bearer {bearer_token}"
        return headers

    async def _request(
        self,
        method: str,
        path: str,
        *,
        bearer_token: str | None = None,
        json: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.request(
                method,
                f"{self.api_base}{path}",
                headers=self._headers(bearer_token=bearer_token),
                json=json,
                params=params,
            )
        if response.is_success:
            payload = response.json()
            if not isinstance(payload, dict):
                raise AirbyteError("Airbyte returned an unexpected response shape.")
            return payload
        try:
            payload = response.json()
        except ValueError:
            payload = response.text
        message = _extract_error_message(payload) if isinstance(payload, dict) else str(payload)
        raise AirbyteError(message or f"Airbyte request failed with status {response.status_code}.")

    async def get_application_token(self) -> str:
        payload = await self._request(
            "POST",
            "/account/applications/token",
            json={
                "client_id": self.client_id,
                "client_secret": self.client_secret,
            },
        )
        access_token = payload.get("access_token")
        if not isinstance(access_token, str) or not access_token.strip():
            raise AirbyteError("Airbyte did not return an application token.")
        return access_token

    async def ensure_customer(self, customer_name: str) -> str:
        """Ensure the Agent Engine customer/workspace exists and return a scoped token.

        Per Airbyte docs, requesting a scoped token auto-creates the customer if needed.
        """
        app_token = await self.get_application_token()
        payload = await self._request(
            "POST",
            "/account/applications/scoped-token",
            bearer_token=app_token,
            json={"customer_name": customer_name},
        )
        access_token = (
            payload.get("access_token")
            or payload.get("token")
            or payload.get("scoped_token")
        )
        if not isinstance(access_token, str) or not access_token.strip():
            raise AirbyteError("Airbyte did not return a scoped token.")
        return access_token

    async def find_connector(
        self,
        *,
        external_user_id: str,
        definition_id: str,
    ) -> dict[str, Any] | None:
        app_token = await self.get_application_token()
        try:
            payload = await self._request(
                "GET",
                "/integrations/connectors",
                bearer_token=app_token,
                params={
                    "external_user_id": external_user_id,
                    "definition_id": definition_id,
                },
            )
        except AirbyteError as exc:
            if "Workspace not found" in str(exc):
                return None
            raise
        data = payload.get("data")
        if not isinstance(data, list) or not data:
            return None
        connector = data[0]
        if not isinstance(connector, dict):
            return None
        return connector

    async def create_connector(
        self,
        *,
        external_user_id: str,
        workspace_name: str,
        definition_id: str,
        name: str,
        credentials: dict[str, Any] | None = None,
        server_side_oauth_secret_id: str | None = None,
    ) -> dict[str, Any]:
        app_token = await self.get_application_token()
        body: dict[str, Any] = {
            "external_user_id": external_user_id,
            "workspace_name": workspace_name,
            "definition_id": definition_id,
            "name": name,
        }
        if credentials:
            body["credentials"] = credentials
        if server_side_oauth_secret_id:
            body["server_side_oauth_secret_id"] = server_side_oauth_secret_id
        return await self._request(
            "POST",
            "/integrations/connectors",
            bearer_token=app_token,
            json=body,
        )

    async def get_or_create_connector(
        self,
        *,
        provider_id: str,
        external_user_id: str,
        workspace_name: str,
        name: str,
        credentials: dict[str, Any],
    ) -> dict[str, Any]:
        definition_id = get_airbyte_definition_id(provider_id)
        if not definition_id:
            raise AirbyteError(f"No Airbyte Agent Connector definition is configured for {provider_id}.")
        await self.ensure_customer(external_user_id)
        existing = await self.find_connector(
            external_user_id=external_user_id,
            definition_id=definition_id,
        )
        if existing:
            return existing
        return await self.create_connector(
            external_user_id=external_user_id,
            workspace_name=workspace_name,
            definition_id=definition_id,
            name=name,
            credentials=credentials,
        )

    async def initiate_oauth(
        self,
        *,
        provider_id: str,
        external_user_id: str,
        redirect_url: str,
    ) -> dict[str, Any]:
        definition_id = get_airbyte_definition_id(provider_id)
        if not definition_id:
            raise AirbyteError(f"No Airbyte Agent Connector definition is configured for {provider_id}.")
        app_token = await self.get_application_token()
        return await self._request(
            "POST",
            "/integrations/connectors/oauth/initiate",
            bearer_token=app_token,
            json={
                "external_user_id": external_user_id,
                "definition_id": definition_id,
                "redirect_url": redirect_url,
            },
        )
