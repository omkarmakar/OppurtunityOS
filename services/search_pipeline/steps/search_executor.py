"""Pipeline step — executes search queries through a SearchProvider."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from database.models.searches import Search
from database.repositories.search_repository import SearchRepository
from plugins.loader import load_bundled_plugins
from services.search import SearchRegistry, SearchResult
from services.search.provider import SearchProvider
from services.search_pipeline.steps.base import PipelineStep

logger = logging.getLogger(__name__)


class SearchExecutor(PipelineStep):
    def __init__(
        self,
        provider_name: str = "dummy",
        result_count: int = 10,
        enabled_plugins: list[str] | None = None,
    ) -> None:
        self._provider_name = provider_name
        self._result_count = max(1, min(result_count, 50))
        self._registry = SearchRegistry.default()
        self._plugin_providers: list[SearchProvider] = []
        self._load_plugin_providers(enabled_plugins)

    def _load_plugin_providers(self, enabled_plugins: list[str] | None) -> None:
        """Discover, filter and instantiate plugin search providers."""
        plugins = load_bundled_plugins(enabled_plugins=enabled_plugins)
        for plug in plugins:
            provider_classes = plug.get_search_providers()
            for pcls in provider_classes:
                try:
                    instance = pcls()
                    self._plugin_providers.append(instance)
                    logger.debug(
                        "Loaded plugin provider %r from plugin %r",
                        instance.name,
                        plug.plugin_name,
                    )
                except Exception as exc:
                    logger.warning(
                        "Failed to instantiate provider %s from plugin %s: %s",
                        pcls.__name__,
                        plug.plugin_name,
                        exc,
                    )

    @property
    def name(self) -> str:
        return "SearchExecutor"

    async def execute(self, ctx: dict[str, Any]) -> dict[str, Any]:
        queries: list[str] = ctx.get("queries", [])
        if not queries:
            ctx["search_results"] = []
            return ctx

        db: Session = ctx["db"]
        profile = ctx["profile"]
        repo = SearchRepository(db)
        now = datetime.now(timezone.utc)

        provider = self._registry.get(self._provider_name)
        all_results: list[SearchResult] = []
        seen_urls: set[str] = set()

        for query in queries:
            query_result_count = 0
            try:
                results = await provider.search(
                    query,
                    count=self._result_count,
                )
                query_result_count = len(results)
                for r in results:
                    if r.url and r.url not in seen_urls:
                        seen_urls.add(r.url)
                        all_results.append(r)
            except Exception as exc:
                logger.warning("Search query '%s' failed: %s", query, exc)

            for plugin_provider in self._plugin_providers:
                try:
                    enhanced_results = await plugin_provider.search(
                        query,
                        count=self._result_count,
                    )
                    query_result_count += len(enhanced_results)
                    for r in enhanced_results:
                        if r.url and r.url not in seen_urls:
                            seen_urls.add(r.url)
                            all_results.append(r)
                except Exception as exc:
                    logger.warning(
                        "Plugin provider '%s' failed for query '%s': %s",
                        plugin_provider.name, query, exc,
                    )

            row = Search(
                user_id=profile.user_id,
                query=query,
                result_count=query_result_count,
                last_run_at=now,
                is_saved=False,
            )
            repo.add(row)

        db.commit()

        ctx["search_results"] = all_results
        return ctx
