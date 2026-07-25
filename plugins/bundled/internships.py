"""Internship Finder — searches for internship opportunities."""

from __future__ import annotations

from plugins.bundled._base import BundledSearchProvider
from plugins.base import BasePlugin


class InternshipSearchProvider(BundledSearchProvider):
    _domain = "internships"
    _keywords = ["internship", "intern", "graduate", "trainee", "placement"]

    @property
    def name(self) -> str:
        return "InternshipFinder"


class InternshipFinderPlugin(BasePlugin):
    plugin_name = "internships"
    plugin_version = "0.1.0"
    plugin_description = "Finds internship opportunities matching the user's profile"
    plugin_author = "OpportunityOS"

    def initialize(self) -> None:
        pass

    def get_search_providers(self) -> list[type]:
        return [InternshipSearchProvider]
