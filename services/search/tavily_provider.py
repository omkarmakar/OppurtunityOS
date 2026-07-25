"""Tavily Search API provider.

Tavily (https://tavily.com) is an AI-focused search API with a recurring
free tier (1,000 credits/month as of 2026), making it the preferred
replacement for Brave Search whose free tier was discontinued in Feb 2026.

API notes (verified against https://docs.tavily.com/documentation/api-reference/endpoint/search):
- Endpoint: POST https://api.tavily.com/search
- Auth: Authorization: Bearer <api_key>  (NOT a body field — the docs
  and some older SDKs vary; the current REST API uses the Bearer header)
- Request body fields used here: query, max_results, search_depth,
  include_raw_content
- Response: results[] where each item has title, url, content (NLP
  summary, ≤500 chars per chunk by default), score (float relevance),
  and optionally raw_content (full page text when requested)
- Rate limits: 429 is returned when credits are exhausted; handled
  explicitly below with a clear error message
"""

from __future__ import annotations

import httpx

from core.config import get_config
from services.search.models import SearchResult
from services.search.provider import SearchProvider

# Tavily's content field is an NLP summary; basic depth returns one
# summary per URL capped around 400-500 characters — comparable to
# Brave's description field.  We truncate conservatively to 500 chars
# so downstream prompt assembly has predictable sizes.
_SNIPPET_MAX_CHARS = 500


class TavilySearchProvider(SearchProvider):
    """Search provider backed by the Tavily Search API.

    Constructor reads ``tavily.api_key`` and ``tavily.base_url`` from
    the application config, exactly mirroring the BraveSearchProvider
    pattern.  Pass *api_key* explicitly to override (useful in tests).
    """

    def __init__(self, api_key: str | None = None) -> None:
        cfg = get_config()
        self._api_key = api_key if api_key is not None else cfg.tavily.api_key
        self._base_url = cfg.tavily.base_url

    @property
    def name(self) -> str:
        return "Tavily"

    async def search(
        self, query: str, count: int = 10, offset: int = 0
    ) -> list[SearchResult]:
        """Execute a Tavily search and return normalised SearchResult objects.

        Args:
            query:  Search query string.
            count:  Maximum results requested (capped at Tavily's max of 20).
            offset: Not natively supported by Tavily; ignored — included in
                    the signature to satisfy the SearchProvider ABC contract.

        Returns:
            List of :class:`~services.search.models.SearchResult` instances.

        Raises:
            RuntimeError: If the API key is not configured.
            httpx.HTTPStatusError: Propagated for non-429 HTTP errors after
                the status check, so callers see the underlying HTTP problem.
            RuntimeError: On HTTP 429 (credit limit exhausted) with a
                descriptive message rather than a bare httpx exception.
        """
        if not self._api_key:
            raise RuntimeError(
                "Tavily API key is not configured. "
                "Set OOS_TAVILY__API_KEY or tavily.api_key in config."
            )

        payload: dict = {
            "query": query,
            "max_results": min(count, 20),
            # basic depth: 1 API credit, one NLP summary per URL, low latency
            "search_depth": "basic",
            # Request raw page content so it can be surfaced via
            # SearchResult.raw without a separate content-extractor fetch.
            # This does NOT change the pipeline contract — raw is an
            # already-existing optional field on SearchResult.
            "include_raw_content": True,
        }
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                self._base_url,
                json=payload,
                headers=headers,
                timeout=15,
            )

        if resp.status_code == 429:
            raise RuntimeError(
                "Tavily API rate limit reached (HTTP 429). "
                "You may have exhausted your monthly credit allowance. "
                "Check your usage at https://app.tavily.com/home."
            )

        resp.raise_for_status()
        data = resp.json()

        results: list[SearchResult] = []
        for item in data.get("results", []):
            snippet = item.get("content", "")
            if len(snippet) > _SNIPPET_MAX_CHARS:
                snippet = snippet[:_SNIPPET_MAX_CHARS].rstrip() + "…"

            # raw_content is the full cleaned page text (markdown or plain),
            # present when include_raw_content=True.  Store it in the raw
            # dict alongside the full item so a future pipeline step can
            # skip re-fetching pages Tavily already returned.
            raw_content = item.get("raw_content")
            raw: dict = {**item}
            if raw_content:
                raw["raw_content"] = raw_content

            results.append(
                SearchResult(
                    title=item.get("title", ""),
                    url=item.get("url", ""),
                    snippet=snippet,
                    source=self.name,
                    raw=raw,
                )
            )

        return results
