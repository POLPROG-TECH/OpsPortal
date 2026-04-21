"""TTL cache service - caches logos, config schemas, and other slow-to-fetch data.

Uses a simple time-based expiration model with per-key storage.
Thread-safe for concurrent access from async handlers.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Any

from opsportal.core.errors import get_logger

logger = get_logger("services.cache")


@dataclass(slots=True)
class CacheEntry:
    key: str
    value: Any
    expires_at: float
    created_at: float


class TTLCache:
    """Simple in-memory cache with per-key TTL expiration."""

    def __init__(self, default_ttl: float = 300.0) -> None:
        self._store: dict[str, CacheEntry] = {}
        self._default_ttl = default_ttl
        self._lock = threading.Lock()
        self._stats = {"hits": 0, "misses": 0, "sets": 0, "evictions": 0}

    def get(self, key: str) -> Any | None:
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                self._stats["misses"] += 1
                return None
            if time.time() > entry.expires_at:
                del self._store[key]
                self._stats["misses"] += 1
                self._stats["evictions"] += 1
                return None
            self._stats["hits"] += 1
            return entry.value

    def set(self, key: str, value: Any, ttl: float | None = None) -> None:
        ttl = ttl if ttl is not None else self._default_ttl
        now = time.time()
        entry = CacheEntry(key=key, value=value, expires_at=now + ttl, created_at=now)
        with self._lock:
            self._store[key] = entry
            self._stats["sets"] += 1

    def delete(self, key: str) -> bool:
        with self._lock:
            return self._store.pop(key, None) is not None

    def clear(self) -> None:
        with self._lock:
            self._store.clear()

    def cleanup(self) -> int:
        """Remove all expired entries. Returns number of entries removed."""
        now = time.time()
        removed = 0
        with self._lock:
            expired_keys = [k for k, v in self._store.items() if now > v.expires_at]
            for k in expired_keys:
                del self._store[k]
                removed += 1
            self._stats["evictions"] += removed
        return removed

    @property
    def stats(self) -> dict[str, int]:
        return dict(self._stats)

    def __len__(self) -> int:
        with self._lock:
            return len(self._store)
