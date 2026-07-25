"""Startup Hiring Finder — searches for job openings at startups."""

from __future__ import annotations

from plugins.bundled._base import BundledSearchProvider
from plugins.base import BasePlugin


class StartupHiringSearchProvider(BundledSearchProvider):
    _domain = "startup_hiring"
    _keywords = [
        "startup hiring", "startup job", "early stage",
        "venture backed", "join startup", "tech startup",
    ]

    @property
    def name(self) -> str:
        return "StartupHiringFinder"


class StartupHiringFinderPlugin(BasePlugin):
    plugin_name = "startup_hiring"
    plugin_version = "0.1.0"
    plugin_description = "Finds job openings at startup companies"
    plugin_author = "OpportunityOS"

    def initialize(self) -> None:
        pass

    def get_search_providers(self) -> list[type]:
        return [StartupHiringSearchProvider]
