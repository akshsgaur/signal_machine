"""In-memory event broker for live chat session updates."""

from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import Any


_subscribers: dict[str, list[asyncio.Queue[dict[str, Any]]]] = defaultdict(list)


def subscribe(session_id: str) -> asyncio.Queue[dict[str, Any]]:
    queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
    _subscribers[session_id].append(queue)
    return queue


def unsubscribe(session_id: str, queue: asyncio.Queue[dict[str, Any]]) -> None:
    subscribers = _subscribers.get(session_id)
    if not subscribers:
        return
    try:
        subscribers.remove(queue)
    except ValueError:
        return
    if not subscribers:
        _subscribers.pop(session_id, None)


async def publish(session_id: str, event: dict[str, Any]) -> None:
    payload = dict(event)
    payload["session_id"] = session_id
    for queue in list(_subscribers.get(session_id, [])):
        await queue.put(payload)
