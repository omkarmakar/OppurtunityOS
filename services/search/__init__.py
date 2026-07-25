"""Search provider plugin package."""

from services.search.dummy_provider import DummyProvider
from services.search.models import SearchResult
from services.search.provider import SearchProvider
from services.search.registry import SearchRegistry

__all__ = [
    "SearchProvider",
    "SearchResult",
    "SearchRegistry",
    "DummyProvider",
]
