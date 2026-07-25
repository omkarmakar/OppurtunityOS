"""In-memory caching layer for AI responses."""

from __future__ import annotations

import hashlib
import json
import threading
import time
from collections import OrderedDict
from typing import Any

from services.ai.models import AIResponse


class AICache:
    def __init__(self, ttl: int = 300, max_size: int = 500) -> None:
        self._ttl = ttl
        self._max_size = max_size
        self._cache: OrderedDict[str, tuple[float, AIResponse]] = OrderedDict()
        self._lock = threading.Lock()

    def _make_key(
        self, messages: list[dict[str, str]], config: dict[str, Any]
    ) -> str:
        raw = json.dumps({"messages": messages, "config": config}, sort_keys=True)
        return hashlib.sha256(raw.encode()).hexdigest()

    def get(
        self, messages: list[dict[str, str]], config: dict[str, Any]
    ) -> AIResponse | None:
        key = self._make_key(messages, config)
        with self._lock:
            if key not in self._cache:
                return None
            expires, response = self._cache[key]
            if time.monotonic() > expires:
                del self._cache[key]
                return None
            self._cache.move_to_end(key)
            return response

    def set(
        self,
        messages: list[dict[str, str]],
        config: dict[str, Any],
        response: AIResponse,
    ) -> None:
        key = self._make_key(messages, config)
        expires = time.monotonic() + self._ttl
        with self._lock:
            self._cache[key] = (expires, response)
            self._cache.move_to_end(key)
            if len(self._cache) > self._max_size:
                self._cache.popitem(last=False)

    def clear(self) -> None:
        with self._lock:
            self._cache.clear()

    @property
    def size(self) -> int:
        now = time.monotonic()
        with self._lock:
            expired = [k for k, (e, _) in self._cache.items() if now > e]
            for k in expired:
                del self._cache[k]
            return len(self._cache)
