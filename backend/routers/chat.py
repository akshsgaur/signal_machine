"""Chat endpoint for multi-source product intelligence."""

from __future__ import annotations

from typing import List

import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from langchain.agents import create_agent
from langchain.chat_models import init_chat_model
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from agents.chat import (
    build_chat_tools,
    CHAT_SYSTEM_PROMPT,
    extract_sources_used,
    resolve_folder_from_query,
)
from db.supabase import (
    add_chat_message,
    create_chat_session,
    list_chat_messages,
    list_chat_sessions,
    touch_chat_session,
)

router = APIRouter(prefix="/chat", tags=["chat"])
logger = logging.getLogger(__name__)


class ChatMessageIn(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    user_id: str
    messages: List[ChatMessageIn]
    session_id: str | None = None
    title: str | None = None
    folder_name: str | None = None


class ChatResponse(BaseModel):
    message: str
    sources_used: List[str]
    session_id: str


class ChatSession(BaseModel):
    id: str
    title: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class ChatMessage(BaseModel):
    id: str
    role: str
    content: str
    sources_used: List[str] = []
    created_at: str | None = None


@router.post("", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Answer a chat query using live integration data."""
    if not request.messages:
        raise HTTPException(status_code=400, detail="messages is required")

    last = request.messages[-1]
    if last.role != "user":
        raise HTTPException(status_code=400, detail="last message must be from user")

    try:
        resolved_folder = request.folder_name
        if not resolved_folder:
            resolved_folder = await resolve_folder_from_query(
                request.user_id, last.content
            )

        tools, tool_to_source, connected_sources = await build_chat_tools(
            request.user_id, resolved_folder
        )
        if not connected_sources:
            return ChatResponse(
                message=(
                    "No integrations are connected yet. Connect Amplitude, Zendesk, "
                    "Productboard, or Linear to ask questions across your data."
                ),
                sources_used=[],
                session_id=request.session_id or "",
            )

        session_id = request.session_id
        if not session_id:
            default_title = (request.title or last.content).strip()
            if len(default_title) > 60:
                default_title = default_title[:57] + "..."
            session_id = await create_chat_session(request.user_id, default_title)

        await add_chat_message(session_id, "user", last.content)

        model = init_chat_model(model="gpt-5.2", temperature=0.2)
        agent = create_agent(
            model,
            tools=tools,
            system_prompt=CHAT_SYSTEM_PROMPT,
        )

        lc_messages = []
        for msg in request.messages:
            if msg.role == "user":
                lc_messages.append(HumanMessage(content=msg.content))
            elif msg.role == "assistant":
                lc_messages.append(AIMessage(content=msg.content))

        result = await agent.ainvoke(
            {"messages": lc_messages},
            config={"recursion_limit": 25},
        )

        message_text = ""
        if isinstance(result, dict) and result.get("messages"):
            last_msg = result["messages"][-1]
            if isinstance(last_msg, (AIMessage, ToolMessage)):
                message_text = last_msg.content
        elif isinstance(result, AIMessage):
            message_text = result.content

        if not message_text:
            message_text = "I could not generate a response. Please try again."

        sources_used = extract_sources_used(result, tool_to_source)
        if not sources_used:
            sources_used = connected_sources

        await add_chat_message(session_id, "assistant", message_text, sources_used)
        await touch_chat_session(session_id)

        return ChatResponse(
            message=message_text, sources_used=sources_used, session_id=session_id
        )
    except Exception as exc:
        logger.exception("Chat error")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/sessions/{user_id}", response_model=List[ChatSession])
async def get_sessions(user_id: str):
    """List recent chat sessions for a user."""
    try:
        return await list_chat_sessions(user_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/sessions/{session_id}/messages", response_model=List[ChatMessage])
async def get_messages(session_id: str):
    """List chat messages for a session."""
    try:
        return await list_chat_messages(session_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
