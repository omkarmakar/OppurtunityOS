"""Token counting utilities for AI models."""

from __future__ import annotations

import threading
from typing import Any


class TokenCounter:
    _instance: TokenCounter | None = None
    _lock: threading.Lock = threading.Lock()

    def __new__(cls) -> TokenCounter:
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if not hasattr(self, "_initialized"):
            self._initialized = True
            self._encoders: dict[str, Any] = {}
            self._encoders_lock = threading.Lock()

    def count_tokens(self, text: str, model: str = "") -> int:
        return self._estimate_tokens(text)

    def _estimate_tokens(self, text: str) -> int:
        return len(text) // 4

    def count_message_tokens(
        self, messages: list[dict[str, str]], model: str = ""
    ) -> int:
        total = 0
        for msg in messages:
            total += self.count_tokens(msg.get("content", ""), model)
            total += self.count_tokens(msg.get("role", ""), model)
        return total
