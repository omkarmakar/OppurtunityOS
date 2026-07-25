"""Competition Finder — searches for competitions and contests."""

from __future__ import annotations

from plugins.bundled._base import BundledSearchProvider
from plugins.base import BasePlugin


class CompetitionSearchProvider(BundledSearchProvider):
    _domain = "competitions"
    _keywords = [
        "competition", "contest", "challenge", "prize",
        "hackathon competition", "case competition", "olympiad",
    ]

    @property
    def name(self) -> str:
        return "CompetitionFinder"


class CompetitionFinderPlugin(BasePlugin):
    plugin_name = "competitions"
    plugin_version = "0.1.0"
    plugin_description = "Finds competitions and contests relevant to the user"
    plugin_author = "OpportunityOS"

    def initialize(self) -> None:
        pass

    def get_search_providers(self) -> list[type]:
        return [CompetitionSearchProvider]
