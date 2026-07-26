"""Runtime plugin discovery and loading via entry points."""

from __future__ import annotations

import importlib.metadata
import logging
from typing import Any

from plugins.base import BasePlugin
from plugins.bundled import ALL_BUNDLED_PLUGINS

logger = logging.getLogger(__name__)

PLUGIN_ENTRY_POINT_GROUP = "opportunityos.plugins"


def discover_entry_point_classes() -> list[type[BasePlugin]]:
    """Discover plugin classes via ``importlib.metadata.entry_points()``.

    Falls back to the hardcoded ``ALL_BUNDLED_PLUGINS`` list when entry
    points are not yet registered (e.g. package not installed editable).
    """
    eps = importlib.metadata.entry_points(group=PLUGIN_ENTRY_POINT_GROUP)
    if eps:
        return [ep.load() for ep in eps]
    logger.warning(
        "No entry points found for group %r \u2014 falling back to "
        "ALL_BUNDLED_PLUGINS (run 'pip install -e .' to register them)",
        PLUGIN_ENTRY_POINT_GROUP,
    )
    return list(ALL_BUNDLED_PLUGINS)


def load_bundled_plugins(
    enabled_plugins: list[str] | None = None,
) -> list[BasePlugin]:
    """Discover, instantiate and filter bundled plugins.

    Parameters
    ----------
    enabled_plugins:
        Whitelist of ``plugin_name`` values to include.

        * ``None`` or ``[]`` (empty) **\u2014 all** discovered plugins
          are returned (opt-out model for bundled first-party plugins).
        * Non-empty list \u2014 only plugins whose ``plugin_name`` is
          in the list are returned.

    Returns
    -------
    list[BasePlugin]
        Instantiated and initialised plugin objects.
    """
    classes = discover_entry_point_classes()
    plugins: list[BasePlugin] = []
    for cls in classes:
        inst = cls()
        inst.initialize()
        plugins.append(inst)

    if enabled_plugins:
        plugins = [p for p in plugins if p.plugin_name in enabled_plugins]

    return plugins


def get_plugin_keywords(
    plugins: list[BasePlugin],
) -> dict[str, list[str]]:
    """Extract the domain keywords from each plugin's search providers.

    Returns a dict mapping ``plugin_name -> [keyword, ...]`` so that
    callers can use the keywords without instantiating providers.
    """
    result: dict[str, list[str]] = {}
    for plug in plugins:
        provider_types = plug.get_search_providers()
        for ptype in provider_types:
            domain = getattr(ptype, "_domain", "")
            keywords = getattr(ptype, "_keywords", [])
            if domain:
                result[plug.plugin_name] = keywords
    return result
