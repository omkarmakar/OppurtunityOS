"""High-level memory service — domain-specific store & recall methods."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from core.config import AppConfig, MemorySettings
from services.memory.models import MemoryEntry, MemoryQuery, MemoryResult, MemoryType
from services.memory.store import ChromaMemoryStore

logger = logging.getLogger(__name__)


class MemoryService:
    """High-level API for storing and retrieving memories.

    Provides convenience methods for each memory domain::

        svc = MemoryService(config)
        svc.initialize()
        svc.store_search(user_id, query, results_count)
        results = await svc.recall("machine learning jobs", user_id)
    """

    def __init__(self, config: AppConfig) -> None:
        self._settings: MemorySettings = config.memory
        self._store: ChromaMemoryStore = ChromaMemoryStore(self._settings)

    # ── lifecycle ───────────────────────────────────────────────────

    def initialize(self) -> None:
        """Initialise the underlying ChromaDB store."""
        self._store.initialize()

    def close(self) -> None:
        """Close the underlying ChromaDB store."""
        self._store.close()

    @property
    def store(self) -> ChromaMemoryStore:
        return self._store

    # ── store helpers ───────────────────────────────────────────────

    def _new_id(self) -> str:
        return str(uuid.uuid4())

    def _ts(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _store_entry(
        self, type_: MemoryType, user_id: str, content: str, title: str = "", **extra: Any
    ) -> str:
        entry_id = self._new_id()
        entry = MemoryEntry(
            id=entry_id,
            type=type_,
            user_id=user_id,
            content=content,
            title=title,
            metadata_=extra,
            created_at=self._ts(),
        )
        self._store.store(entry)
        return entry_id

    # ── domain-specific store methods ───────────────────────────────

    def store_search(
        self, user_id: str, query: str, result_count: int = 0
    ) -> str:
        """Remember a search the user performed."""
        content = f"Search query: {query}"
        return self._store_entry(
            MemoryType.SEARCH, user_id, content,
            title=f"Searched: {query[:80]}",
            query=query,
            result_count=result_count,
        )

    def store_feedback(
        self, user_id: str, opportunity_id: str, rating: int, comment: str = "",
    ) -> str:
        """Remember user feedback on an opportunity."""
        content = f"Feedback on {opportunity_id}: rating={rating}"
        if comment:
            content += f" — {comment}"
        return self._store_entry(
            MemoryType.FEEDBACK, user_id, content,
            title=f"Rating {rating}/5",
            opportunity_id=opportunity_id,
            rating=rating,
            comment=comment,
        )

    def store_bookmark(
        self, user_id: str, opportunity_id: str, title: str, url: str = "", notes: str = "",
    ) -> str:
        """Remember a bookmarked opportunity."""
        content = f"Bookmarked: {title}"
        if notes:
            content += f" — {notes}"
        return self._store_entry(
            MemoryType.BOOKMARK, user_id, content,
            title=f"Bookmark: {title[:60]}",
            opportunity_id=opportunity_id,
            url=url,
            notes=notes,
        )

    def store_rejected(
        self, user_id: str, opportunity_id: str, title: str, reason: str = "",
    ) -> str:
        """Remember an opportunity the user rejected."""
        content = f"Rejected: {title}"
        if reason:
            content += f" — Reason: {reason}"
        return self._store_entry(
            MemoryType.REJECTED, user_id, content,
            title=f"Rejected: {title[:60]}",
            opportunity_id=opportunity_id,
            reason=reason,
        )

    def store_prompt(self, user_id: str, prompt_text: str) -> str:
        """Remember a frequently used prompt."""
        content = f"Prompt: {prompt_text}"
        return self._store_entry(
            MemoryType.PROMPT, user_id, content,
            title=f"Prompt: {prompt_text[:60]}",
            prompt_text=prompt_text,
        )

    # ── recall methods ──────────────────────────────────────────────

    def recall(
        self, text: str, user_id: str | None = None,
        type_: MemoryType | str | None = None, top_k: int | None = None,
    ) -> list[MemoryResult]:
        """Semantic search across all stored memories."""
        query = MemoryQuery(
            text=text,
            user_id=user_id,
            type=type_,
            top_k=top_k or self._settings.top_k,
        )
        return self._store.search(query)

    def recall_recent(self, user_id: str, limit: int = 20) -> list[MemoryResult]:
        """Return the most recent memories for a user."""
        return self._store.get_recent(user_id, limit=limit)

    def recall_by_type(
        self, user_id: str, type_: MemoryType | str, limit: int = 20
    ) -> list[MemoryResult]:
        """Return recent memories of a specific type."""
        return self._store.get_by_type(user_id, type_, limit=limit)
