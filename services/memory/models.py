"""Data models for memory entries and queries."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class MemoryType(str, Enum):
    """The kind of memory being stored."""

    SEARCH = "search"
    FEEDBACK = "feedback"
    BOOKMARK = "bookmark"
    REJECTED = "rejected"
    PROMPT = "prompt"


@dataclass
class MemoryEntry:
    """A single memory to be stored in the vector store.

    Attributes:
        id: Unique identifier (UUID string).
        type: Which domain this memory belongs to.
        user_id: The user who owns this memory.
        content: The primary text to embed and search over.
        title: Short human-readable label.
        metadata_: Arbitrary key-value payload (e.g. query, rating, url).
        created_at: ISO-8601 timestamp.
    """

    id: str
    type: MemoryType | str
    user_id: str
    content: str
    title: str = ""
    metadata_: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class MemoryQuery:
    """A query against the vector store."""

    text: str
    user_id: str | None = None
    type: MemoryType | str | None = None
    top_k: int = 10
    threshold: float | None = None


@dataclass
class MemoryResult:
    """A single result from a vector store query."""

    id: str
    type: MemoryType | str
    user_id: str
    content: str
    title: str
    metadata_: dict[str, Any]
    created_at: str
    distance: float
