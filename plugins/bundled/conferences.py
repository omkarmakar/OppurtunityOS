"""Conference Finder — searches for upcoming conferences."""

from __future__ import annotations

from plugins.bundled._base import BundledSearchProvider
from plugins.base import BasePlugin


class ConferenceSearchProvider(BundledSearchProvider):
    _domain = "conferences"
    _keywords = [
        "conference", "summit", "symposium", "convention",
        "call for papers", "cfp", "registration open",
    ]

    @property
    def name(self) -> str:
        return "ConferenceFinder"


class ConferenceFinderPlugin(BasePlugin):
    plugin_name = "conferences"
    plugin_version = "0.1.0"
    plugin_description = "Finds upcoming conferences in the user's field"
    plugin_author = "OpportunityOS"

    def initialize(self) -> None:
        pass

    def get_search_providers(self) -> list[type]:
        return [ConferenceSearchProvider]
