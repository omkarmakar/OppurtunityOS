"""Brave Search API provider."""

from __future__ import annotations

import httpx

from core.config import get_config
from services.search.models import SearchResult
from services.search.provider import SearchProvider

BRAVE_HEADERS = {
    "Accept": "application/json",
    "Accept-Encoding": "gzip",
}


class BraveSearchProvider(SearchProvider):
    """Search provider backed by the Brave Search API."""

    def __init__(self, api_key: str | None = None) -> None:
        cfg = get_config()
        self._api_key = api_key or cfg.brave_search.api_key
        self._base_url = cfg.brave_search.base_url

    @property
    def name(self) -> str:
        return "Brave"

    async def search(self, query: str, count: int = 10, offset: int = 0) -> list[SearchResult]:
        if not self._api_key:
            msg = "Brave Search API key is not configured. Set OOS_BRAVE_SEARCH__API_KEY or brave_search.api_key in config."
            raise RuntimeError(msg)

        params: dict[str, str | int] = {
            "q": query,
            "count": min(count, 20),
            "offset": offset,
        }
        headers = {**BRAVE_HEADERS, "X-Subscription-Token": self._api_key}

        async with httpx.AsyncClient() as client:
            resp = await client.get(self._base_url, params=params, headers=headers, timeout=15)
            resp.raise_for_status()
            data = resp.json()

        results: list[SearchResult] = []
        for item in data.get("web", {}).get("results", []):
            results.append(
                SearchResult(
                    title=item.get("title", ""),
                    url=item.get("url", ""),
                    snippet=item.get("description", ""),
                    source=self.name,
                    raw=item,
                )
            )
        return results
