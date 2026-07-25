"""Extension point type definitions for the Plugin SDK.

These ABCs define the 5 contract interfaces a plugin can implement.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class RankingProvider(ABC):
    """Ranks opportunities by relevance to a profile.

    Register via BasePlugin.get_ranking_providers().
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable name, used as the registry key (lowercased)."""

    @abstractmethod
    async def rank(self, opportunities: list[dict], profile: dict) -> list[dict]:
        """Return opportunities sorted by score descending.

        Each dict in the returned list must include a 'ranking_score' float.
        """


class DataSourceProvider(ABC):
    """Fetches or imports opportunities from an external system.

    Register via BasePlugin.get_data_sources().
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable name, used as the registry key."""

    @property
    @abstractmethod
    def source_type(self) -> str:
        """Type identifier stored in the Source model (e.g. 'rss', 'api')."""

    @abstractmethod
    async def fetch(self, config: dict) -> list[dict]:
        """Return a list of raw opportunity dicts.

        Each dict should contain at minimum:
          - title: str
          - url: str (optional)
          - description: str (optional)
        """

    @abstractmethod
    def get_config_schema(self) -> dict:
        """Return a JSON Schema dict describing the required config fields."""


class NotificationChannel(ABC):
    """A delivery channel for notifications.

    Register via BasePlugin.get_notification_channels().
    """

    @property
    @abstractmethod
    def channel_name(self) -> str:
        """Used as the registry key (e.g. 'slack', 'telegram')."""

    @abstractmethod
    def send(self, user_id: str, title: str, message: str, **kwargs: Any) -> bool:
        """Deliver a notification. Returns True on success."""


class PagePlugin(ABC):
    """A GUI page that appears in the sidebar and stacked widget.

    Register via BasePlugin.get_gui_pages().
    """

    @property
    @abstractmethod
    def title(self) -> str:
        """Page title shown in the sidebar and page header."""

    @property
    @abstractmethod
    def icon(self) -> str:
        """Unicode glyph for the sidebar button (e.g. '\u2609')."""

    @property
    def order(self) -> int:
        """Sidebar position; built-in pages use 0-7, plugins default to 99."""
        return 99

    @abstractmethod
    def create_widget(self) -> Any:
        """Return a QWidget instance for this page."""
