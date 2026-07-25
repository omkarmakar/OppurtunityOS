"""Research Paper Finder — searches for academic papers and publications."""

from __future__ import annotations

from plugins.bundled._base import BundledSearchProvider
from plugins.base import BasePlugin


class ResearchPaperSearchProvider(BundledSearchProvider):
    _domain = "research_papers"
    _keywords = [
        "research paper", "publication", "arxiv", "academic",
        "journal", "proceedings", "preprint",
    ]

    @property
    def name(self) -> str:
        return "ResearchPaperFinder"


class ResearchPaperFinderPlugin(BasePlugin):
    plugin_name = "research_papers"
    plugin_version = "0.1.0"
    plugin_description = "Finds academic papers and publications relevant to the user"
    plugin_author = "OpportunityOS"

    def initialize(self) -> None:
        pass

    def get_search_providers(self) -> list[type]:
        return [ResearchPaperSearchProvider]
