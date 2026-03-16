"""Small in-memory TTL cache for dashboard read paths."""

from __future__ import annotations

import time
from dataclasses import dataclass
from threading import Lock
from typing import Any


@dataclass
class CacheEntry:
    value: Any
    expires_at: float | None


class TTLCache:
    def __init__(self) -> None:
        self._entries: dict[str, CacheEntry] = {}
        self._lock = Lock()

    def get(self, key: str) -> Any | None:
        now = time.monotonic()
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                return None
            if entry.expires_at is not None and entry.expires_at <= now:
                self._entries.pop(key, None)
                return None
            return entry.value

    def set(self, key: str, value: Any, ttl_seconds: float | None = None) -> Any:
        expires_at = None if ttl_seconds is None else time.monotonic() + ttl_seconds
        with self._lock:
            self._entries[key] = CacheEntry(value=value, expires_at=expires_at)
        return value

    def delete(self, key: str) -> None:
        with self._lock:
            self._entries.pop(key, None)

    def delete_prefix(self, prefix: str) -> None:
        with self._lock:
            for key in list(self._entries.keys()):
                if key.startswith(prefix):
                    self._entries.pop(key, None)


cache = TTLCache()
