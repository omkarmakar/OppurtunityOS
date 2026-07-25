"""Pipeline step — executes search queries through a SearchProvider."""

from __future__ import annotations

import logging
from typing import Any

from services.search import SearchRegistry, SearchResult
from services.search_pipeline.steps.base import PipelineStep

logger = logging.getLogger(__name__)


class SearchExecutor(PipelineStep):
    def __init__(
        self,
        provider_name: str = "dummy",
        result_count: int = 10,
    ) -> None:
        self._provider_name = provider_name
        self._result_count = max(1, min(result_count, 50))
        self._registry = SearchRegistry.default()

    @property
    def name(self) -> str:
        return "SearchExecutor"

    async def execute(self, ctx: dict[str, Any]) -> dict[str, Any]:
        queries: list[str] = ctx.get("queries", [])
        if not queries:
            ctx["search_results"] = []
            return ctx

        provider = self._registry.get(self._provider_name)
        all_results: list[SearchResult] = []
        seen_urls: set[str] = set()

        for query in queries:
            try:
                results = await provider.search(
                    query,
                    count=self._result_count,
                )
                for r in results:
                    if r.url and r.url not in seen_urls:
                        seen_urls.add(r.url)
                        all_results.append(r)
            except Exception as exc:
                logger.warning("Search query '%s' failed: %s", query, exc)

        ctx["search_results"] = all_results
        return ctx
