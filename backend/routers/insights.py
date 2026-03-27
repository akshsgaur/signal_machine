"""Customer insights upload + listing via Morphik."""

from __future__ import annotations

import json
import os
from typing import List

import httpx
from fastapi import APIRouter, HTTPException, UploadFile, File, Form

from db.supabase import fetch_all, fetch_one

router = APIRouter(prefix="/insights", tags=["insights"])

MORPHIK_BASE_URL = os.getenv("MORPHIK_BASE_URL", "https://api.morphik.ai")
MORPHIK_API_KEY = os.getenv("MORPHIK_API_KEY")


def _require_morphik_key() -> str:
    if not MORPHIK_API_KEY:
        raise HTTPException(status_code=500, detail="MORPHIK_API_KEY is not configured")
    return MORPHIK_API_KEY


@router.post("/upload")
async def upload_customer_docs(
    user_id: str = Form(...),
    files: List[UploadFile] = File(...),
    folder_name: str | None = Form(None),
):
    """Upload one or more customer interview documents to Morphik."""
    api_key = _require_morphik_key()
    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded")

    uploaded = []
    async with httpx.AsyncClient(timeout=60) as client:
        for upload in files:
            content = await upload.read()
            if not content:
                continue
            metadata = {
                "user_id": user_id,
                "source": "customer_interview",
            }
            data = {
                "metadata": json.dumps(metadata),
                "use_colpali": "true",
                "end_user_id": user_id,
            }
            if folder_name:
                data["folder_name"] = folder_name
            files_payload = {
                "file": (upload.filename or "upload", content, upload.content_type),
            }
            resp = await client.post(
                f"{MORPHIK_BASE_URL}/ingest/file",
                headers={"Authorization": f"Bearer {api_key}"},
                data=data,
                files=files_payload,
            )
            if resp.status_code >= 400:
                raise HTTPException(status_code=resp.status_code, detail=resp.text)
            uploaded.append(resp.json())

    return {"uploaded": uploaded}


@router.post("/folders")
async def create_folder(user_id: str = Form(...), name: str = Form(...)):
    """Create a customer insights folder for a user."""
    if not name.strip():
        raise HTTPException(status_code=400, detail="Folder name is required")
    row = await fetch_one(
        """
        INSERT INTO insights_folders (user_id, name)
        VALUES (%s, %s)
        RETURNING id, user_id, name, created_at
        """,
        (user_id, name.strip()),
    )
    if row is None:
        raise HTTPException(status_code=500, detail="Failed to create folder")
    return row


@router.get("/folders/{user_id}")
async def list_folders(user_id: str):
    """List folders for a user."""
    return await fetch_all(
        """
        SELECT id, name, created_at
        FROM insights_folders
        WHERE user_id = %s
        ORDER BY created_at ASC
        """,
        (user_id,),
    )


@router.get("/list/{user_id}")
async def list_customer_docs(
    user_id: str,
    limit: int = 50,
    skip: int = 0,
    folder_name: str | None = None,
):
    """List customer interview documents for a user."""
    api_key = _require_morphik_key()
    document_filters = {
        "user_id": {"$eq": user_id},
        "source": {"$eq": "customer_interview"},
    }

    payload = {
        "skip": skip,
        "limit": limit,
        "document_filters": document_filters,
        "fields": [
            "document_id",
            "filename",
            "created_at",
            "updated_at",
            "status",
            "folder_name",
            "metadata",
        ],
        "sort_by": "created_at",
        "sort_direction": "desc",
        "include_total_count": True,
        "include_status_counts": True,
        "completed_only": False,
    }
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{MORPHIK_BASE_URL}/documents/list_docs",
            headers={"Authorization": f"Bearer {api_key}"},
            params={"end_user_id": user_id, "folder_name": folder_name}
            if folder_name
            else {"end_user_id": user_id},
            json=payload,
        )
        if resp.status_code >= 400:
            raise HTTPException(status_code=resp.status_code, detail=resp.text)
        return resp.json()
