"""In-memory event broker for streaming chat title updates."""

from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import Any


_subscribers: dict[str, list[asyncio.Queue[dict[str, Any]]]] = defaultdict(list)
_snapshots: dict[str, dict[str, Any]] = {}


def subscribe(session_id: str) -> asyncio.Queue[dict[str, Any]]:
    """Subscribe to title events for a chat session."""
    queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
    _subscribers[session_id].append(queue)
    return queue


def unsubscribe(session_id: str, queue: asyncio.Queue[dict[str, Any]]) -> None:
    """Remove a queue from the subscriber list for a chat session."""
    subscribers = _subscribers.get(session_id)
    if not subscribers:
        return
    try:
        subscribers.remove(queue)
    except ValueError:
        return
    if not subscribers:
        _subscribers.pop(session_id, None)


def get_snapshot(session_id: str) -> dict[str, Any] | None:
    """Return the latest title event snapshot for a chat session."""
    snapshot = _snapshots.get(session_id)
    if snapshot is None:
        return None
    return dict(snapshot)


async def publish(session_id: str, event: dict[str, Any]) -> None:
    """Publish a title event to all active subscribers and retain the latest snapshot."""
    payload = dict(event)
    payload["session_id"] = session_id
    _snapshots[session_id] = payload
    for queue in list(_subscribers.get(session_id, [])):
        await queue.put(payload)
