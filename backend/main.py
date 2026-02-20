"""Signal FastAPI application entry point."""

import logging

from dotenv import load_dotenv

load_dotenv()

# Suppress the ClosedResourceError noise from mcp's streamable_http GET-stream
# cleanup. This is a known mcp SDK bug (1.26.x) where the background SSE
# listener tries to write to a stream that's already been closed during session
# teardown. The error is caught internally and doesn't affect correctness.
logging.getLogger("mcp.client.streamable_http").setLevel(logging.CRITICAL)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers import integrations, pipeline

app = FastAPI(title="Signal PM Intelligence Platform", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(integrations.router)
app.include_router(pipeline.router)


@app.get("/health")
async def health():
    return {"status": "ok"}
