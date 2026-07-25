"""Dummy search provider for development and testing."""

from __future__ import annotations

from services.search.models import SearchResult
from services.search.provider import SearchProvider


class DummyProvider(SearchProvider):
    """Returns hardcoded results — no external dependencies."""

    @property
    def name(self) -> str:
        return "Dummy"

    async def search(self, query: str, count: int = 10, offset: int = 0) -> list[SearchResult]:
        results = [
            SearchResult(
                title=f"{query} — Result {i + 1}",
                url=f"https://example.com/result/{i + 1}",
                snippet=f"This is a dummy search result for \"{query}\" (#{i + 1}).",
                source=self.name,
            )
            for i in range(min(count, 5))
        ]
        return results[offset:offset + count]
