"""Abstract base plugin with extension-point hooks."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BasePlugin(ABC):
    """Base class for all plugins.

    Subclasses set metadata as class attributes and override
    ``get_*`` methods to declare what extension points they provide.

    Example::

        class MyPlugin(BasePlugin):
            plugin_name = "my_plugin"
            plugin_version = "0.1.0"

            def initialize(self) -> None:
                pass

            def get_search_providers(self) -> list[type]:
                return [MySearchProvider]
    """

    # ── Metadata ────────────────────────────────────────────────────
    plugin_name: str = ""
    plugin_version: str = "0.1.0"
    plugin_description: str = ""
    plugin_author: str = ""

    # ── Lifecycle ───────────────────────────────────────────────────

    @abstractmethod
    def initialize(self) -> None:
        """Register hooks and set up state. Called after discovery."""

    def on_enable(self) -> None:
        """Called when the plugin transitions from disabled to enabled."""

    def on_disable(self) -> None:
        """Called when the plugin transitions from enabled to disabled."""

    # ── Extension point registration hooks ──────────────────────────

    def get_search_providers(self) -> list[type]:
        """Return SearchProvider subclasses provided by this plugin."""
        return []

    def get_ranking_providers(self) -> list[type]:
        """Return RankingProvider subclasses provided by this plugin."""
        return []

    def get_data_sources(self) -> list[type]:
        """Return DataSourceProvider subclasses provided by this plugin."""
        return []

    def get_notification_channels(self) -> list[type]:
        """Return NotificationChannel subclasses provided by this plugin."""
        return []

    def get_gui_pages(self) -> list[type]:
        """Return PagePlugin subclasses provided by this plugin."""
        return []
