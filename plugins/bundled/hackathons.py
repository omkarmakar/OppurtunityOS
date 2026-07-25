"""Hackathon Finder — searches for upcoming hackathons."""

from __future__ import annotations

from plugins.bundled._base import BundledSearchProvider
from plugins.base import BasePlugin


class HackathonSearchProvider(BundledSearchProvider):
    _domain = "hackathons"
    _keywords = [
        "hackathon", "coding competition", "buildathon",
        "hack night", "online hackathon", "registration",
    ]

    @property
    def name(self) -> str:
        return "HackathonFinder"


class HackathonFinderPlugin(BasePlugin):
    plugin_name = "hackathons"
    plugin_version = "0.1.0"
    plugin_description = "Finds upcoming hackathons and coding competitions"
    plugin_author = "OpportunityOS"

    def initialize(self) -> None:
        pass

    def get_search_providers(self) -> list[type]:
        return [HackathonSearchProvider]
