"""Signal FastAPI application entry point."""

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers import integrations, pipeline

app = FastAPI(title="Signal PM Intelligence Platform", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(integrations.router)
app.include_router(pipeline.router)


@app.get("/health")
async def health():
    return {"status": "ok"}
