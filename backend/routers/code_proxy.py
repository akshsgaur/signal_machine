"""Proxy access to code-server with signed tokens."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
import asyncio
from typing import Dict
from urllib.parse import urlencode, urljoin

import httpx
import websockets
from fastapi import APIRouter, HTTPException, Request, WebSocket
from fastapi.responses import JSONResponse, Response, StreamingResponse

router = APIRouter(prefix="/code", tags=["code-proxy"])

CODE_SERVER_URL = os.getenv("CODE_SERVER_URL", "").rstrip("/")
CODE_PROXY_SECRET = os.getenv("CODE_PROXY_SECRET", "")
CODE_TOKEN_TTL_SECONDS = int(os.getenv("CODE_TOKEN_TTL_SECONDS", "900"))
CODE_PROXY_PUBLIC_BASE = os.getenv("CODE_PROXY_PUBLIC_BASE", "").rstrip("/")


def _require_proxy_env() -> None:
    if not CODE_SERVER_URL or not CODE_PROXY_SECRET:
        raise HTTPException(status_code=500, detail="Code proxy is not configured.")


def _sign_payload(payload: Dict) -> str:
    data = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    sig = hmac.new(CODE_PROXY_SECRET.encode("utf-8"), data, hashlib.sha256).hexdigest()
    token = base64.urlsafe_b64encode(data).decode("utf-8")
    return f"{token}.{sig}"


def _verify_token(token: str, expected_user_id: str) -> Dict:
    try:
        b64, sig = token.split(".", 1)
        data = base64.urlsafe_b64decode(b64.encode("utf-8"))
        expected_sig = hmac.new(
            CODE_PROXY_SECRET.encode("utf-8"), data, hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(sig, expected_sig):
            raise ValueError("Invalid signature")
        payload = json.loads(data.decode("utf-8"))
    except Exception as exc:
        raise HTTPException(status_code=401, detail=f"Invalid token: {exc}") from exc

    if payload.get("user_id") != expected_user_id:
        raise HTTPException(status_code=401, detail="Token user mismatch.")
    if payload.get("exp", 0) < int(time.time()):
        raise HTTPException(status_code=401, detail="Token expired.")
    return payload


def _filtered_request_headers(headers: Dict[str, str]) -> Dict[str, str]:
    blocked = {
        "host",
        "origin",
        "referer",
        "content-length",
        "if-none-match",
        "if-modified-since",
    }
    return {k: v for k, v in headers.items() if k.lower() not in blocked}


def _filtered_response_headers(headers: Dict[str, str]) -> Dict[str, str]:
    blocked = {
        "content-encoding",
        "transfer-encoding",
        "connection",
        "content-length",
        "etag",
        "last-modified",
    }
    return {k: v for k, v in headers.items() if k.lower() not in blocked}


def _get_cookie_token_user(request: Request) -> tuple[str, str]:
    token = request.query_params.get("token") or request.cookies.get("code_token") or ""
    user_id = request.query_params.get("user_id") or request.cookies.get("code_user") or ""
    return token, user_id


@router.get("/session")
async def get_code_session(user_id: str):
    _require_proxy_env()
    exp = int(time.time()) + CODE_TOKEN_TTL_SECONDS
    token = _sign_payload({"user_id": user_id, "exp": exp})
    path = f"/code/u/{user_id}/?token={token}"
    url = f"{CODE_PROXY_PUBLIC_BASE}{path}" if CODE_PROXY_PUBLIC_BASE else path
    return JSONResponse({"url": url, "expires_at": exp})


@router.api_route(
    "/u/{user_id}/{path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
)
async def proxy_code(request: Request, user_id: str, path: str):
    _require_proxy_env()
    token = request.query_params.get("token") or request.cookies.get("code_token") or ""
    _verify_token(token, user_id)

    upstream = urljoin(f"{CODE_SERVER_URL}/", path)
    params = dict(request.query_params)
    params.pop("token", None)
    if params:
        upstream = f"{upstream}?{urlencode(params)}"

    async with httpx.AsyncClient(timeout=None) as client:
        resp = await client.request(
            request.method,
            upstream,
            headers=_filtered_request_headers(dict(request.headers)),
            content=await request.body(),
        )
        body = await resp.aread()
        response = Response(
            content=body,
            status_code=resp.status_code,
            headers=_filtered_response_headers(dict(resp.headers)),
        )
        response.headers["cache-control"] = "no-store"
        if request.query_params.get("token"):
            response.set_cookie("code_token", token, path="/", httponly=True, samesite="lax")
            response.set_cookie("code_user", user_id, path="/", httponly=True, samesite="lax")
        return response


@router.websocket("/u/{user_id}/{path:path}")
async def proxy_code_ws(websocket: WebSocket, user_id: str, path: str):
    _require_proxy_env()
    token = websocket.query_params.get("token") or websocket.cookies.get("code_token") or ""
    _verify_token(token, user_id)

    await websocket.accept()

    ws_url = CODE_SERVER_URL.replace("http://", "ws://").replace("https://", "wss://")
    if not ws_url:
        await websocket.close(code=1011)
        return

    params = dict(websocket.query_params)
    params.pop("token", None)
    query = f"?{urlencode(params)}" if params else ""
    upstream = f"{ws_url}/{path}{query}"

    async with websockets.connect(upstream) as upstream_ws:
        async def to_upstream():
            try:
                while True:
                    message = await websocket.receive()
                    if "text" in message:
                        await upstream_ws.send(message["text"])
                    elif "bytes" in message:
                        await upstream_ws.send(message["bytes"])
            except Exception:
                await upstream_ws.close()

        async def to_client():
            try:
                async for message in upstream_ws:
                    if isinstance(message, bytes):
                        await websocket.send_bytes(message)
                    else:
                        await websocket.send_text(message)
            except Exception:
                await websocket.close()

        await asyncio.gather(to_upstream(), to_client())


@router.api_route("/login", methods=["GET", "POST"])
async def proxy_login(request: Request):
    _require_proxy_env()
    token, user_id = _get_cookie_token_user(request)
    if not token or not user_id:
        raise HTTPException(status_code=401, detail="Missing code session token.")
    _verify_token(token, user_id)
    upstream = f"{CODE_SERVER_URL}/login"
    async with httpx.AsyncClient(timeout=None) as client:
        resp = await client.request(
            request.method,
            upstream,
            headers=_filtered_request_headers(dict(request.headers)),
            content=await request.body(),
        )
        body = await resp.aread()
        return Response(
            content=body,
            status_code=resp.status_code,
            headers=_filtered_response_headers(dict(resp.headers)),
        )


@router.api_route("/static/{path:path}", methods=["GET"])
async def proxy_static(request: Request, path: str):
    _require_proxy_env()
    token, user_id = _get_cookie_token_user(request)
    if not token or not user_id:
        raise HTTPException(status_code=401, detail="Missing code session token.")
    _verify_token(token, user_id)
    upstream = f"{CODE_SERVER_URL}/static/{path}"
    async with httpx.AsyncClient(timeout=None) as client:
        resp = await client.get(
            upstream,
            headers=_filtered_request_headers(dict(request.headers)),
        )
        body = await resp.aread()
        return Response(
            content=body,
            status_code=resp.status_code,
            headers=_filtered_response_headers(dict(resp.headers)),
        )


@router.api_route("/vscode/{path:path}", methods=["GET"])
async def proxy_vscode_assets(request: Request, path: str):
    _require_proxy_env()
    token, user_id = _get_cookie_token_user(request)
    if not token or not user_id:
        raise HTTPException(status_code=401, detail="Missing code session token.")
    _verify_token(token, user_id)
    upstream = f"{CODE_SERVER_URL}/vscode/{path}"
    async with httpx.AsyncClient(timeout=None) as client:
        resp = await client.get(
            upstream,
            headers=_filtered_request_headers(dict(request.headers)),
        )
        body = await resp.aread()
        return Response(
            content=body,
            status_code=resp.status_code,
            headers=_filtered_response_headers(dict(resp.headers)),
        )
