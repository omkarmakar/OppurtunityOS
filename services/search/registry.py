"""Search provider registry — plugin discovery and management."""

from __future__ import annotations

import logging

from services.search.brave_provider import BraveSearchProvider
from services.search.dummy_provider import DummyProvider
from services.search.jobboard_provider import JobBoardProvider
from services.search.provider import SearchProvider
from services.search.tavily_provider import TavilySearchProvider

logger = logging.getLogger(__name__)


class SearchRegistry:
    """Registry of available search providers.

    Usage::
        registry = SearchRegistry()
        provider = registry.get("brave")
        results = await provider.search("python jobs")
    """

    def __init__(self) -> None:
        self._providers: dict[str, SearchProvider] = {}

    def register(self, provider: SearchProvider) -> None:
        self._providers[provider.name.lower()] = provider

    def get(self, name: str) -> SearchProvider:
        key = name.lower()
        if key not in self._providers:
            msg = f"Unknown search provider: {name}. Available: {list(self._providers)}"
            raise KeyError(msg)
        return self._providers[key]

    def list(self) -> list[str]:
        return list(self._providers)

    @classmethod
    def default(cls) -> SearchRegistry:
        """Create a registry pre-loaded with built-in providers."""
        registry = cls()
        registry.register(DummyProvider())
        try:
            registry.register(JobBoardProvider())
            logger.debug("JobBoardProvider registered for real job board searches")
        except Exception as exc:
            logger.debug("JobBoardProvider not available: %s", exc)
        try:
            registry.register(BraveSearchProvider())
        except Exception as exc:
            logger.debug("BraveSearchProvider not available: %s", exc)
        try:
            registry.register(TavilySearchProvider())
        except Exception as exc:
            logger.debug("TavilySearchProvider not available: %s", exc)
        return registry
