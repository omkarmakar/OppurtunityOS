"""Generic in-memory query cache with TTL and thread safety."""

from __future__ import annotations

import threading
import time
from typing import Any, Callable, TypeVar

T = TypeVar("T")


class QueryCache:
    """Thread-safe TTL cache for expensive queries.

    Usage::

        cache = QueryCache[str](ttl=60)
        result = cache.get_or_set("user_dashboard_42", lambda: compute_expensive())
    """

    def __init__(self, ttl: float = 30.0, max_size: int = 200) -> None:
        self._ttl = ttl
        self._max_size = max_size
        self._cache: dict[str, tuple[float, Any]] = {}
        self._lock = threading.Lock()

    def get(self, key: str) -> Any | None:
        with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                return None
            expires, value = entry
            if time.monotonic() > expires:
                del self._cache[key]
                return None
            return value

    def set(self, key: str, value: Any) -> None:
        expires = time.monotonic() + self._ttl
        with self._lock:
            self._cache[key] = (expires, value)
            if len(self._cache) > self._max_size:
                oldest = next(iter(self._cache))
                del self._cache[oldest]

    def get_or_set(self, key: str, factory: Callable[[], T]) -> T:
        existing = self.get(key)
        if existing is not None:
            return existing
        value = factory()
        self.set(key, value)
        return value

    def invalidate(self, key: str) -> None:
        with self._lock:
            self._cache.pop(key, None)

    def invalidate_pattern(self, prefix: str) -> None:
        with self._lock:
            keys = [k for k in self._cache if k.startswith(prefix)]
            for k in keys:
                del self._cache[k]

    def clear(self) -> None:
        with self._lock:
            self._cache.clear()

    @property
    def size(self) -> int:
        with self._lock:
            now = time.monotonic()
            expired = [k for k, (e, _) in self._cache.items() if now > e]
            for k in expired:
                del self._cache[k]
            return len(self._cache)
