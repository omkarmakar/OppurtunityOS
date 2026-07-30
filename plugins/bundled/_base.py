"""Shared base for bundled finder plugins.

BundledSearchProvider is a mixin that lazily resolves the configured
search provider (Tavily → Dummy fallback) so each plugin only needs
to override the ``name`` property and ``_enhance_query()``.
"""

from __future__ import annotations

import logging
from typing import Any

from core.config import get_config
from services.search.models import SearchResult
from services.search.provider import SearchProvider
from services.search.registry import SearchRegistry

logger = logging.getLogger(__name__)


class BundledSearchProvider(SearchProvider):
    """Base for bundled search providers.

    Subclasses set ``_domain`` (used as ``source`` on results) and
    ``_keywords`` (terms appended to every query), and optionally
    override ``_enhance_query()`` for custom query crafting.
    """

    _domain: str = ""
    _keywords: list[str] = []

    def __init__(self, inner: SearchProvider | None = None) -> None:
        self._inner = inner

    async def _resolve_inner(self) -> SearchProvider:
        if self._inner is not None:
            return self._inner
        cfg = get_config()
        default_provider = cfg.pipeline_search_provider or "tavily"
        registry = SearchRegistry.default()
        try:
            self._inner = registry.get(default_provider)
        except KeyError:
            logger.warning(
                "Configured search provider %r not available; falling back to dummy. "
                "Set pipeline_search_provider to a registered provider.",
                default_provider,
            )
            self._inner = registry.get("dummy")
        return self._inner

    def _enhance_query(self, query: str) -> str:
        parts = [query, *self._keywords]
        return " ".join(parts)

    async def search(
        self, query: str, count: int = 10, offset: int = 0
    ) -> list[SearchResult]:
        inner = await self._resolve_inner()
        enhanced = self._enhance_query(query)
        results = await inner.search(enhanced, count, offset)
        for r in results:
            r.source = self._domain or self.name.lower()
        return results
