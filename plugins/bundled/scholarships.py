"""Scholarship Finder — searches for scholarship opportunities."""

from __future__ import annotations

from plugins.bundled._base import BundledSearchProvider
from plugins.base import BasePlugin


class ScholarshipSearchProvider(BundledSearchProvider):
    _domain = "scholarships"
    _keywords = [
        "scholarship", "financial aid", "fellowship", "grant",
        "funding", "merit based",
    ]

    @property
    def name(self) -> str:
        return "ScholarshipFinder"


class ScholarshipFinderPlugin(BasePlugin):
    plugin_name = "scholarships"
    plugin_version = "0.1.0"
    plugin_description = "Finds scholarship opportunities matching the user's profile"
    plugin_author = "OpportunityOS"

    def initialize(self) -> None:
        pass

    def get_search_providers(self) -> list[type]:
        return [ScholarshipSearchProvider]
