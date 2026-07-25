"""Job Finder — searches for job opportunities matching the user's profile."""

from __future__ import annotations

from plugins.bundled._base import BundledSearchProvider
from plugins.base import BasePlugin


class JobSearchProvider(BundledSearchProvider):
    _domain = "jobs"
    _keywords = ["job", "hiring", "career", "apply", "position"]

    @property
    def name(self) -> str:
        return "JobFinder"


class JobFinderPlugin(BasePlugin):
    plugin_name = "jobs"
    plugin_version = "0.1.0"
    plugin_description = "Finds job opportunities matching the user's profile"
    plugin_author = "OpportunityOS"

    def initialize(self) -> None:
        pass

    def get_search_providers(self) -> list[type]:
        return [JobSearchProvider]
