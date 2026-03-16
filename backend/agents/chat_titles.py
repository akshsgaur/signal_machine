"""Helpers for generating and streaming chat session titles."""

from __future__ import annotations

import asyncio
import os
import re
from typing import Awaitable, Callable

from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage


TITLE_MODEL = os.getenv("CHAT_TITLE_MODEL", "gpt-5-mini")
MAX_WORDS = 6
STREAM_DELAY_SECONDS = 0.03


def _normalize_whitespace(value: str) -> str:
    return " ".join(value.strip().split())


def _strip_wrapper_quotes(value: str) -> str:
    return value.strip().strip("\"'`")


def _to_title_case(value: str) -> str:
    return " ".join(word.capitalize() for word in value.split())


def _sanitize_title(raw_title: str) -> str:
    title = _normalize_whitespace(raw_title)
    title = _strip_wrapper_quotes(title)
    title = re.sub(r"^[Tt]itle:\s*", "", title)
    title = title.rstrip(".,:;!?")
    words = title.split()
    if len(words) > MAX_WORDS:
        words = words[:MAX_WORDS]
    title = " ".join(words)
    title = _to_title_case(title)
    return title.strip()


def _fallback_title(prompt: str) -> str:
    text = re.sub(r"\s+", " ", prompt).strip()
    words = re.findall(r"[A-Za-z0-9]+", text)
    if not words:
        return "General Product Chat"
    selected = words[: min(MAX_WORDS, max(3, min(4, len(words))))]
    return _to_title_case(" ".join(selected))


async def generate_chat_title(prompt: str) -> str:
    """Generate a short conversation title from the first user prompt."""
    fallback = _fallback_title(prompt)
    try:
        model = init_chat_model(model=TITLE_MODEL, temperature=0)
        response = await model.ainvoke(
            [
                HumanMessage(
                    content=(
                        "Generate a concise 3-4 word title for this conversation.\n"
                        "Rules:\n"
                        "- Plain text only\n"
                        "- No quotes\n"
                        "- No markdown\n"
                        "- No trailing punctuation\n"
                        "- Maximum 6 words\n"
                        "- Always produce a title\n\n"
                        f"User request:\n{prompt}"
                    )
                )
            ]
        )
        content = getattr(response, "content", "")
        if isinstance(content, list):
            content = " ".join(
                part.get("text", "") for part in content if isinstance(part, dict)
            )
        title = _sanitize_title(str(content))
        return title or fallback
    except Exception:
        return fallback


async def stream_chat_title(
    prompt: str,
    publish: Callable[[dict], Awaitable[None]],
) -> str:
    """Generate a title and emit incremental prefix updates."""
    await publish({"type": "title_start"})
    title = await generate_chat_title(prompt)
    last_content = ""
    for index in range(1, len(title) + 1):
        content = title[:index]
        if content == last_content:
            continue
        last_content = content
        await publish({"type": "title_delta", "content": content})
        await asyncio.sleep(STREAM_DELAY_SECONDS)
    return title
