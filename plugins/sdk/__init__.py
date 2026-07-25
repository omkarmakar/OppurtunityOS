"""Plugin SDK — public API for plugin authors.

Usage:
    from opportunityos_plugin_sdk import BasePlugin, SearchProvider, RankingProvider
"""

from plugins.base import BasePlugin
from plugins.sdk.types import (
    DataSourceProvider,
    NotificationChannel,
    PagePlugin,
    RankingProvider,
)

__all__ = [
    "BasePlugin",
    "RankingProvider",
    "DataSourceProvider",
    "NotificationChannel",
    "PagePlugin",
]
