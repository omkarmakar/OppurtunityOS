"""Abstract search provider interface."""

from __future__ import annotations

from abc import ABC, abstractmethod

from services.search.models import SearchResult


class SearchProvider(ABC):
    """Abstract base class for all search providers."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable provider name."""

    @abstractmethod
    async def search(self, query: str, count: int = 10, offset: int = 0) -> list[SearchResult]:
        """Execute a search and return raw results."""
