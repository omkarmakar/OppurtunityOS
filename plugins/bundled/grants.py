"""Grant Finder — searches for grant funding opportunities."""

from __future__ import annotations

from plugins.bundled._base import BundledSearchProvider
from plugins.base import BasePlugin


class GrantSearchProvider(BundledSearchProvider):
    _domain = "grants"
    _keywords = [
        "grant", "funding opportunity", "research grant",
        "government grant", "foundation grant", "proposal",
    ]

    @property
    def name(self) -> str:
        return "GrantFinder"


class GrantFinderPlugin(BasePlugin):
    plugin_name = "grants"
    plugin_version = "0.1.0"
    plugin_description = "Finds grant funding opportunities for research and projects"
    plugin_author = "OpportunityOS"

    def initialize(self) -> None:
        pass

    def get_search_providers(self) -> list[type]:
        return [GrantSearchProvider]
