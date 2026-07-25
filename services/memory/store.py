"""Low-level ChromaDB wrapper — client lifecycle and CRUD."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from core.config import MemorySettings
from services.memory.models import MemoryEntry, MemoryQuery, MemoryResult, MemoryType

logger = logging.getLogger(__name__)


class ChromaMemoryStore:
    """Wraps a ChromaDB collection for storing and retrieving memories.

    Usage::

        store = ChromaMemoryStore(settings)
        store.store(MemoryEntry(...))
        results = store.search(MemoryQuery(text="machine learning"))
    """

    def __init__(self, settings: MemorySettings) -> None:
        self._settings = settings
        self._client: Any = None
        self._collection: Any = None

    # ── lifecycle ───────────────────────────────────────────────────

    def initialize(self) -> None:
        """Create or connect to the ChromaDB collection (lazy import)."""
        import chromadb
        from chromadb.config import Settings as ChromaSettings
        from chromadb.errors import NotFoundError

        persist = self._settings.persist_directory.strip()
        if persist:
            self._client = chromadb.PersistentClient(
                path=persist,
                settings=ChromaSettings(anonymized_telemetry=False),
            )
            logger.info("ChromaDB persistent client at %s", persist)
        else:
            self._client = chromadb.EphemeralClient(
                settings=ChromaSettings(anonymized_telemetry=False),
            )
            logger.info("ChromaDB ephemeral client (in-memory)")

        name = self._settings.collection_name
        try:
            self._collection = self._client.get_collection(name)
            logger.info("Reusing existing ChromaDB collection '%s'", name)
        except NotFoundError:
            self._collection = self._client.create_collection(name)
            logger.info("Created ChromaDB collection '%s'", name)

    def close(self) -> None:
        """Tear down the ChromaDB client."""
        if self._client:
            self._client = None
            self._collection = None
            logger.info("ChromaDB client closed")

    @property
    def collection(self) -> Any:
        if self._collection is None:
            msg = "ChromaDB not initialized — call initialize() first"
            raise RuntimeError(msg)
        return self._collection

    @property
    def is_initialized(self) -> bool:
        return self._collection is not None

    # ── write ───────────────────────────────────────────────────────

    def store(self, entry: MemoryEntry) -> None:
        """Insert or update a single memory entry."""
        self.collection.add(
            ids=[entry.id],
            documents=[entry.content],
            metadatas=[self._build_metadata(entry)],
        )

    def store_batch(self, entries: list[MemoryEntry]) -> None:
        """Insert or update multiple memory entries efficiently."""
        if not entries:
            return
        self.collection.add(
            ids=[e.id for e in entries],
            documents=[e.content for e in entries],
            metadatas=[self._build_metadata(e) for e in entries],
        )

    def delete(self, entry_id: str) -> None:
        """Remove a single memory entry by ID."""
        self.collection.delete(ids=[entry_id])

    def delete_by_user(self, user_id: str) -> None:
        """Remove all memory entries for a given user."""
        self.collection.delete(where={"user_id": user_id})

    # ── read ────────────────────────────────────────────────────────

    def search(self, query: MemoryQuery) -> list[MemoryResult]:
        """Semantic search across stored memories."""
        filters: list[dict[str, Any]] = []
        if query.user_id:
            filters.append({"user_id": query.user_id})
        if query.type:
            t = query.type.value if isinstance(query.type, MemoryType) else query.type
            filters.append({"type": t})

        where: dict[str, Any] | None = None
        if len(filters) == 1:
            where = filters[0]
        elif len(filters) > 1:
            where = {"$and": filters}

        results = self.collection.query(
            query_texts=[query.text],
            n_results=query.top_k,
            where=where,
        )
        return self._parse_results(results)

    def get_recent(self, user_id: str, limit: int = 20) -> list[MemoryResult]:
        """Return the most recent entries for a user (no semantic filtering)."""
        results = self.collection.get(
            where={"user_id": user_id},
            limit=limit,
        )
        return self._parse_get_results(results)

    def get_by_type(
        self, user_id: str, type_: MemoryType | str, limit: int = 20
    ) -> list[MemoryResult]:
        """Return recent entries of a specific type for a user."""
        t = type_.value if isinstance(type_, MemoryType) else type_
        results = self.collection.get(
            where={"$and": [{"user_id": user_id}, {"type": t}]},
            limit=limit,
        )
        return self._parse_get_results(results)

    def count(self, user_id: str | None = None) -> int:
        """Return the number of stored entries, optionally filtered by user."""
        if user_id:
            results = self.collection.get(where={"user_id": user_id})
            return len(results.get("ids", []))
        return self.collection.count()

    # ── internals ───────────────────────────────────────────────────

    def _build_metadata(self, entry: MemoryEntry) -> dict[str, Any]:
        return {
            "type": entry.type.value if isinstance(entry.type, MemoryType) else entry.type,
            "user_id": entry.user_id,
            "title": entry.title,
            "created_at": entry.created_at,
            **entry.metadata_,
        }

    def _parse_results(self, raw: dict[str, Any]) -> list[MemoryResult]:
        if not raw.get("ids") or not raw["ids"][0]:
            return []
        results: list[MemoryResult] = []
        for i, doc_id in enumerate(raw["ids"][0]):
            meta = (raw["metadatas"] or [None])[0][i] if raw.get("metadatas") else {}
            dist = (raw["distances"] or [None])[0][i] if raw.get("distances") else 0.0
            results.append(
                MemoryResult(
                    id=doc_id,
                    type=meta.get("type", ""),
                    user_id=meta.get("user_id", ""),
                    content=(raw["documents"] or [""])[0][i] if raw.get("documents") else "",
                    title=meta.get("title", ""),
                    metadata_={k: v for k, v in meta.items() if k not in ("type", "user_id", "title", "created_at")},
                    created_at=meta.get("created_at", ""),
                    distance=dist,
                )
            )
        return results

    def _parse_get_results(self, raw: dict[str, Any]) -> list[MemoryResult]:
        if not raw.get("ids"):
            return []
        results: list[MemoryResult] = []
        for i, doc_id in enumerate(raw["ids"]):
            meta = (raw["metadatas"] or [{}])[i] if raw.get("metadatas") else {}
            results.append(
                MemoryResult(
                    id=doc_id,
                    type=meta.get("type", ""),
                    user_id=meta.get("user_id", ""),
                    content=(raw["documents"] or [""])[i] if raw.get("documents") else "",
                    title=meta.get("title", ""),
                    metadata_={k: v for k, v in meta.items() if k not in ("type", "user_id", "title", "created_at")},
                    created_at=meta.get("created_at", ""),
                    distance=0.0,
                )
            )
        return results
