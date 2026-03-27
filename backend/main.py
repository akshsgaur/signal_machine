"""Signal FastAPI application entry point."""

import logging
import os

from dotenv import load_dotenv

load_dotenv()

# Suppress the ClosedResourceError noise from mcp's streamable_http GET-stream
# cleanup. This is a known mcp SDK bug (1.26.x) where the background SSE
# listener tries to write to a stream that's already been closed during session
# teardown. The error is caught internally and doesn't affect correctness.
logging.getLogger("mcp.client.streamable_http").setLevel(logging.CRITICAL)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers import admin, chat, code_proxy, dashboard, insights, integrations, macroscope, pipeline, slack

app = FastAPI(title="Signal PM Intelligence Platform", version="0.1.0")

cors_origins = [
    "http://localhost:3000",
    "http://localhost:3001",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:3001",
    "https://8171-2601-647-4900-4f60-d486-1686-cb2f-f4fd.ngrok-free.app",
]

cors_from_env = os.getenv("CORS_ALLOW_ORIGINS", "")
if cors_from_env:
    cors_origins.extend([origin.strip() for origin in cors_from_env.split(",") if origin.strip()])

frontend_url = os.getenv("FRONTEND_URL")
if frontend_url:
    cors_origins.append(frontend_url.strip())

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(dict.fromkeys(cors_origins)),
    allow_origin_regex=r"^https?://(localhost|127\\.0\\.0\\.1)(:3000|:3001)?$|^https://.*\\.up\\.railway\\.app$|^https://.*\\.vercel\\.app$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(integrations.router)
app.include_router(pipeline.router)
app.include_router(chat.router)
app.include_router(admin.router)
app.include_router(insights.router)
app.include_router(slack.router)
app.include_router(code_proxy.router)
app.include_router(dashboard.router)
app.include_router(macroscope.router)


@app.get("/health")
async def health():
    return {"status": "ok"}
