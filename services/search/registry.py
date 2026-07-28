"""Search provider registry — plugin discovery and management."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from services.search.brave_provider import BraveSearchProvider
from services.search.dummy_provider import DummyProvider
from services.search.jobboard_provider import JobBoardProvider
from services.search.provider import SearchProvider
from services.search.tavily_provider import TavilySearchProvider

if TYPE_CHECKING:
    from plugins.base import BasePlugin
    from plugins.bundled._base import BundledSearchProvider

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

    def register_plugin_providers(
        self,
        plugins: list[BasePlugin],
        enabled_names: list[str] | None = None,
    ) -> None:
        """Register SearchProviders from the given plugin list.

        Each plugin's ``get_search_providers()`` is called to obtain
        provider *classes*, which are then instantiated and registered
        under their ``.name``.

        Parameters
        ----------
        plugins:
            Already-loaded plugin instances.
        enabled_names:
            Optional whitelist of ``plugin_name`` values whose providers
            should be registered.  ``None`` or empty means *all*.
        """
        for plug in plugins:
            if enabled_names and plug.plugin_name not in enabled_names:
                continue
            provider_classes = plug.get_search_providers()
            for pcls in provider_classes:
                try:
                    instance = pcls()
                    self.register(instance)
                    logger.debug(
                        "Registered plugin provider %r from plugin %r",
                        instance.name,
                        plug.plugin_name,
                    )
                except Exception as exc:
                    logger.warning(
                        "Failed to register provider %s from plugin %s: %s",
                        pcls.__name__,
                        plug.plugin_name,
                        exc,
                    )
