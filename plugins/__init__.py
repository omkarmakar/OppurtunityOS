"""Plugin system package."""

from __future__ import annotations

from plugins.base import BasePlugin
from plugins.bundled import ALL_BUNDLED_PLUGINS
from plugins.sdk import DataSourceProvider, NotificationChannel, PagePlugin, RankingProvider

__all__ = [
    "ALL_BUNDLED_PLUGINS",
    "BasePlugin",
    "RankingProvider",
    "DataSourceProvider",
    "NotificationChannel",
    "PagePlugin",
]
