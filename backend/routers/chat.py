"""Chat endpoint for multi-source product intelligence."""

from __future__ import annotations

import asyncio
import json
from typing import List

import logging
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from langchain.agents import create_agent
from langchain.chat_models import init_chat_model
from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage, ToolMessage

from agents.chat_activity import format_tool_activity, summarize_activity
from agents.chat import (
    build_chat_tools,
    CHAT_SYSTEM_PROMPT,
    extract_sources_used,
    resolve_folder_from_query,
)
from agents.chat_title_streams import get_snapshot, publish, subscribe, unsubscribe
from agents.chat_titles import stream_chat_title
from db.supabase import (
    add_chat_message,
    create_chat_session,
    list_chat_messages,
    list_chat_sessions,
    touch_chat_session,
    update_chat_session_title,
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


class ChatActivityStep(BaseModel):
    step_id: str
    label: str
    status: str


class StartChatSessionRequest(BaseModel):
    user_id: str
    first_message: str
    title: str | None = None


class StartChatSessionResponse(BaseModel):
    session_id: str
    title: str


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


def _extract_chunk_text(chunk: object) -> str:
    """Extract human-readable text from a streamed model chunk."""
    if not isinstance(chunk, AIMessageChunk):
        return ""
    content = getattr(chunk, "content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict):
                text = item.get("text")
                if isinstance(text, str):
                    parts.append(text)
        return "".join(parts)
    return ""


def _extract_final_response_from_event(event: dict) -> str:
    """Best-effort extraction of the final assistant message from stream events."""
    data = event.get("data") or {}
    output = data.get("output")
    if isinstance(output, dict):
        messages = output.get("messages") or []
        if isinstance(messages, list):
            for message in reversed(messages):
                if isinstance(message, AIMessage):
                    content = getattr(message, "content", "")
                    if isinstance(content, str) and content.strip():
                        return content
                    if isinstance(content, list):
                        parts: list[str] = []
                        for item in content:
                            if isinstance(item, dict):
                                text = item.get("text")
                                if isinstance(text, str):
                                    parts.append(text)
                        joined = "".join(parts).strip()
                        if joined:
                            return joined
    return ""


async def _generate_and_persist_title(session_id: str, first_message: str) -> None:
    """Generate a streamed title for a new chat session and persist it."""
    try:
        title = await stream_chat_title(
            first_message,
            lambda event: publish(session_id, event),
        )
        await update_chat_session_title(session_id, title)
        await publish(session_id, {"type": "title_complete", "title": title})
    except Exception:
        logger.exception("Chat title generation failed")
        await publish(session_id, {"type": "title_error"})


@router.post("/sessions", response_model=StartChatSessionResponse)
async def start_chat_session(request: StartChatSessionRequest):
    """Create a new chat session and begin streaming its generated title."""
    first_message = request.first_message.strip()
    if not first_message:
        raise HTTPException(status_code=400, detail="first_message is required")

    try:
        session_id = await create_chat_session(
            request.user_id,
            (request.title or "Product chat").strip() or "Product chat",
        )
        asyncio.create_task(_generate_and_persist_title(session_id, first_message))
        return StartChatSessionResponse(session_id=session_id, title="Product chat")
    except Exception as exc:
        logger.exception("Chat session start error")
        raise HTTPException(status_code=500, detail=str(exc))


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

        session_id = request.session_id
        if not session_id:
            default_title = (request.title or "Product chat").strip() or "Product chat"
            session_id = await create_chat_session(request.user_id, default_title)
            asyncio.create_task(_generate_and_persist_title(session_id, last.content))

        tools, tool_to_source, connected_sources = await build_chat_tools(
            request.user_id, resolved_folder
        )
        if not connected_sources:
            message_text = (
                "No chat-capable integrations are connected yet. Connect one of the "
                "available MCP-backed sources from the integrations page and try again."
            )
            await add_chat_message(session_id, "user", last.content)
            await add_chat_message(session_id, "assistant", message_text, [])
            await touch_chat_session(session_id)
            return ChatResponse(
                message=message_text,
                sources_used=[],
                session_id=session_id,
            )

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

        await add_chat_message(session_id, "assistant", message_text, sources_used)
        await touch_chat_session(session_id)

        return ChatResponse(
            message=message_text, sources_used=sources_used, session_id=session_id
        )
    except Exception as exc:
        logger.exception("Chat error")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/stream")
async def chat_stream(request: ChatRequest):
    """Stream chat activity and final response as SSE."""
    if not request.messages:
        raise HTTPException(status_code=400, detail="messages is required")

    last = request.messages[-1]
    if last.role != "user":
        raise HTTPException(status_code=400, detail="last message must be from user")

    async def event_generator():
        session_id = request.session_id
        try:
            resolved_folder = request.folder_name
            if not resolved_folder:
                resolved_folder = await resolve_folder_from_query(
                    request.user_id, last.content
                )

            if not session_id:
                default_title = (request.title or "Product chat").strip() or "Product chat"
                session_id = await create_chat_session(request.user_id, default_title)
                asyncio.create_task(_generate_and_persist_title(session_id, last.content))

            await add_chat_message(session_id, "user", last.content)
            yield f"data: {json.dumps({'type': 'thinking_start', 'session_id': session_id})}\n\n"

            tools, tool_to_source, connected_sources = await build_chat_tools(
                request.user_id, resolved_folder
            )
            if not connected_sources:
                message_text = (
                    "No chat-capable integrations are connected yet. Connect one of the "
                    "available MCP-backed sources from the integrations page and try again."
                )
                await add_chat_message(session_id, "assistant", message_text, [])
                await touch_chat_session(session_id)
                yield f"data: {json.dumps({'type': 'activity_complete', 'session_id': session_id, 'summary': 'Thought through the request', 'tool_count': 0})}\n\n"
                yield f"data: {json.dumps({'type': 'final_response', 'session_id': session_id, 'message': message_text, 'sources_used': []})}\n\n"
                yield f"data: {json.dumps({'type': 'done', 'session_id': session_id})}\n\n"
                return

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

            active_step_id: str | None = None
            active_tool_name: str | None = None
            step_counter = 0
            labels_used: list[str] = []
            sources_seen: list[str] = []
            final_response_chunks: list[str] = []
            final_response_text = ""
            final_result: object = None

            async for event in agent.astream_events(
                {"messages": lc_messages},
                config={"recursion_limit": 25},
                version="v2",
            ):
                event_type = event.get("event")
                if event_type == "on_tool_start":
                    if active_step_id and active_tool_name:
                        previous_label = format_tool_activity(active_tool_name, tool_to_source)
                        yield f"data: {json.dumps({'type': 'activity_step', 'session_id': session_id, 'step_id': active_step_id, 'label': previous_label, 'status': 'complete'})}\n\n"
                    tool_name = event.get("name") or "tool"
                    step_counter += 1
                    active_step_id = str(step_counter)
                    active_tool_name = str(tool_name)
                    label = format_tool_activity(active_tool_name, tool_to_source)
                    labels_used.append(label)
                    source = tool_to_source.get(active_tool_name)
                    if source:
                        sources_seen.append(source)
                    yield f"data: {json.dumps({'type': 'activity_step', 'session_id': session_id, 'step_id': active_step_id, 'label': label, 'status': 'active'})}\n\n"
                    continue

                if event_type == "on_tool_end" and active_step_id and active_tool_name:
                    label = format_tool_activity(active_tool_name, tool_to_source)
                    yield f"data: {json.dumps({'type': 'activity_step', 'session_id': session_id, 'step_id': active_step_id, 'label': label, 'status': 'complete'})}\n\n"
                    active_step_id = None
                    active_tool_name = None
                    continue

                if event_type == "on_tool_error":
                    label = "Tool check failed, continuing"
                    step_counter += 1
                    yield f"data: {json.dumps({'type': 'activity_step', 'session_id': session_id, 'step_id': str(step_counter), 'label': label, 'status': 'complete'})}\n\n"
                    active_step_id = None
                    active_tool_name = None
                    continue

                if event_type == "on_chat_model_stream":
                    data = event.get("data") or {}
                    chunk_text = _extract_chunk_text(data.get("chunk"))
                    if chunk_text:
                        final_response_chunks.append(chunk_text)
                    continue

                if event_type == "on_chain_end" and not event.get("parent_ids"):
                    final_result = (event.get("data") or {}).get("output")
                    extracted = _extract_final_response_from_event(event)
                    if extracted:
                        final_response_text = extracted

            if active_step_id and active_tool_name:
                label = format_tool_activity(active_tool_name, tool_to_source)
                yield f"data: {json.dumps({'type': 'activity_step', 'session_id': session_id, 'step_id': active_step_id, 'label': label, 'status': 'complete'})}\n\n"

            if not final_response_text:
                final_response_text = "".join(final_response_chunks).strip()
            if not final_response_text and isinstance(final_result, AIMessage):
                content = getattr(final_result, "content", "")
                if isinstance(content, str):
                    final_response_text = content

            if not final_response_text:
                final_response_text = "I could not generate a response. Please try again."

            sources_used = extract_sources_used(final_result, tool_to_source)
            summary, tool_count = summarize_activity(labels_used, sources_seen)

            await add_chat_message(session_id, "assistant", final_response_text, sources_used)
            await touch_chat_session(session_id)

            yield f"data: {json.dumps({'type': 'activity_complete', 'session_id': session_id, 'summary': summary, 'tool_count': tool_count})}\n\n"
            yield f"data: {json.dumps({'type': 'final_response', 'session_id': session_id, 'message': final_response_text, 'sources_used': sources_used})}\n\n"
            yield f"data: {json.dumps({'type': 'done', 'session_id': session_id})}\n\n"
        except Exception as exc:
            logger.exception("Chat stream error")
            if session_id:
                yield f"data: {json.dumps({'type': 'error', 'session_id': session_id, 'message': str(exc)})}\n\n"
                yield f"data: {json.dumps({'type': 'done', 'session_id': session_id})}\n\n"
            else:
                yield f"data: {json.dumps({'type': 'error', 'message': str(exc)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/sessions/{user_id}", response_model=List[ChatSession])
async def get_sessions(user_id: str):
    """List recent chat sessions for a user."""
    try:
        return await list_chat_sessions(user_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/sessions/{session_id}/title-stream")
async def stream_title(session_id: str):
    """SSE stream of incremental title updates for a chat session."""

    async def event_generator():
        queue = subscribe(session_id)
        try:
            snapshot = get_snapshot(session_id)
            if snapshot:
                yield f"data: {json.dumps(snapshot)}\n\n"
                if snapshot["type"] in {"title_complete", "title_error"}:
                    return

            while True:
                event = await queue.get()
                yield f"data: {json.dumps(event)}\n\n"
                if event["type"] in {"title_complete", "title_error"}:
                    break
        finally:
            unsubscribe(session_id, queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/sessions/{session_id}/messages", response_model=List[ChatMessage])
async def get_messages(session_id: str):
    """List chat messages for a session."""
    try:
        return await list_chat_messages(session_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
