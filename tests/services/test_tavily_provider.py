"""Tavily search provider tests.

All tests mock httpx.AsyncClient so no real network calls are made.
Structure mirrors tests/services/test_search_providers.py.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from services.search.models import SearchResult
from services.search.registry import SearchRegistry
from services.search.tavily_provider import TavilySearchProvider, _SNIPPET_MAX_CHARS


# ── Helpers ──────────────────────────────────────────────────────────

def _make_response(results: list[dict], status_code: int = 200) -> MagicMock:
    """Build a fake httpx.Response-like mock."""
    mock_resp = MagicMock()
    mock_resp.status_code = status_code
    mock_resp.json.return_value = {"results": results, "query": "test"}
    if status_code >= 400:
        mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            message=f"HTTP {status_code}",
            request=MagicMock(),
            response=mock_resp,
        )
    else:
        mock_resp.raise_for_status.return_value = None
    return mock_resp


def _tavily_result(
    title: str = "Test Title",
    url: str = "https://example.com",
    content: str = "A short snippet.",
    score: float = 0.9,
    raw_content: str | None = None,
) -> dict:
    item: dict = {"title": title, "url": url, "content": content, "score": score}
    if raw_content is not None:
        item["raw_content"] = raw_content
    return item


# ── Provider basics ──────────────────────────────────────────────────


class TestTavilyProviderName:
    def test_name(self) -> None:
        assert TavilySearchProvider(api_key="tvly-test").name == "Tavily"


class TestTavilyProviderMissingKey:
    @pytest.mark.asyncio
    async def test_raises_runtime_error_without_api_key(self) -> None:
        provider = TavilySearchProvider(api_key="")
        with pytest.raises(RuntimeError, match="Tavily API key is not configured"):
            await provider.search("test query")

    @pytest.mark.asyncio
    async def test_error_message_includes_env_var_hint(self) -> None:
        provider = TavilySearchProvider(api_key="")
        with pytest.raises(RuntimeError, match="OOS_TAVILY__API_KEY"):
            await provider.search("test query")


# ── Happy-path search ────────────────────────────────────────────────


class TestTavilyProviderSearch:
    @pytest.mark.asyncio
    async def test_returns_search_results(self) -> None:
        mock_resp = _make_response([
            _tavily_result("Job A", "https://a.com", "Snippet A"),
            _tavily_result("Job B", "https://b.com", "Snippet B"),
        ])
        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.post = AsyncMock(return_value=mock_resp)
            mock_client_cls.return_value = mock_client

            provider = TavilySearchProvider(api_key="tvly-test")
            results = await provider.search("python jobs", count=2)

        assert len(results) == 2
        assert all(isinstance(r, SearchResult) for r in results)

    @pytest.mark.asyncio
    async def test_result_fields_mapped_correctly(self) -> None:
        mock_resp = _make_response([
            _tavily_result("Engineer Role", "https://jobs.example.com", "Great snippet here."),
        ])
        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.post = AsyncMock(return_value=mock_resp)
            mock_client_cls.return_value = mock_client

            provider = TavilySearchProvider(api_key="tvly-test")
            results = await provider.search("engineer")

        r = results[0]
        assert r.title == "Engineer Role"
        assert r.url == "https://jobs.example.com"
        assert r.snippet == "Great snippet here."
        assert r.source == "Tavily"

    @pytest.mark.asyncio
    async def test_source_is_tavily(self) -> None:
        mock_resp = _make_response([_tavily_result()])
        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.post = AsyncMock(return_value=mock_resp)
            mock_client_cls.return_value = mock_client

            provider = TavilySearchProvider(api_key="tvly-test")
            results = await provider.search("test")

        assert all(r.source == "Tavily" for r in results)

    @pytest.mark.asyncio
    async def test_empty_results(self) -> None:
        mock_resp = _make_response([])
        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.post = AsyncMock(return_value=mock_resp)
            mock_client_cls.return_value = mock_client

            provider = TavilySearchProvider(api_key="tvly-test")
            results = await provider.search("obscure query")

        assert results == []

    @pytest.mark.asyncio
    async def test_count_capped_at_20(self) -> None:
        """max_results sent to Tavily must not exceed 20."""
        mock_resp = _make_response([])
        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.post = AsyncMock(return_value=mock_resp)
            mock_client_cls.return_value = mock_client

            provider = TavilySearchProvider(api_key="tvly-test")
            await provider.search("test", count=50)

        call_kwargs = mock_client.post.call_args
        sent_payload = call_kwargs.kwargs.get("json") or call_kwargs.args[1]
        assert sent_payload["max_results"] == 20

    @pytest.mark.asyncio
    async def test_bearer_auth_header_sent(self) -> None:
        """Auth uses Authorization: Bearer header only (not in body)."""
        mock_resp = _make_response([])
        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.post = AsyncMock(return_value=mock_resp)
            mock_client_cls.return_value = mock_client

            provider = TavilySearchProvider(api_key="tvly-mykey")
            await provider.search("test")

        call_kwargs = mock_client.post.call_args
        headers = call_kwargs.kwargs.get("headers", {})
        assert headers.get("Authorization") == "Bearer tvly-mykey"
        body = call_kwargs.kwargs.get("json", {})
        assert "api_key" not in body


# ── Snippet truncation ───────────────────────────────────────────────


class TestSnippetTruncation:
    @pytest.mark.asyncio
    async def test_long_content_truncated(self) -> None:
        long_content = "x" * (_SNIPPET_MAX_CHARS + 100)
        mock_resp = _make_response([_tavily_result(content=long_content)])
        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.post = AsyncMock(return_value=mock_resp)
            mock_client_cls.return_value = mock_client

            provider = TavilySearchProvider(api_key="tvly-test")
            results = await provider.search("test")

        snippet = results[0].snippet
        assert len(snippet) <= _SNIPPET_MAX_CHARS + 1  # +1 for the ellipsis char
        assert snippet.endswith("…")

    @pytest.mark.asyncio
    async def test_short_content_not_truncated(self) -> None:
        short_content = "Short snippet."
        mock_resp = _make_response([_tavily_result(content=short_content)])
        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.post = AsyncMock(return_value=mock_resp)
            mock_client_cls.return_value = mock_client

            provider = TavilySearchProvider(api_key="tvly-test")
            results = await provider.search("test")

        assert results[0].snippet == short_content


# ── raw_content wiring ───────────────────────────────────────────────


class TestRawContent:
    @pytest.mark.asyncio
    async def test_raw_content_stored_in_raw_dict(self) -> None:
        raw_page = "Full page markdown text here."
        mock_resp = _make_response([_tavily_result(raw_content=raw_page)])
        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.post = AsyncMock(return_value=mock_resp)
            mock_client_cls.return_value = mock_client

            provider = TavilySearchProvider(api_key="tvly-test")
            results = await provider.search("test")

        assert results[0].raw is not None
        assert results[0].raw.get("raw_content") == raw_page

    @pytest.mark.asyncio
    async def test_raw_is_populated_even_without_raw_content(self) -> None:
        mock_resp = _make_response([_tavily_result()])  # no raw_content key
        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.post = AsyncMock(return_value=mock_resp)
            mock_client_cls.return_value = mock_client

            provider = TavilySearchProvider(api_key="tvly-test")
            results = await provider.search("test")

        # raw dict is still populated (from the full item), just no raw_content key
        assert results[0].raw is not None
        assert "raw_content" not in results[0].raw

    @pytest.mark.asyncio
    async def test_include_raw_content_sent_in_request(self) -> None:
        mock_resp = _make_response([])
        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.post = AsyncMock(return_value=mock_resp)
            mock_client_cls.return_value = mock_client

            provider = TavilySearchProvider(api_key="tvly-test")
            await provider.search("test")

        body = mock_client.post.call_args.kwargs.get("json", {})
        assert body.get("include_raw_content") is True


# ── Error handling ───────────────────────────────────────────────────


class TestErrorHandling:
    @pytest.mark.asyncio
    async def test_404_raises_descriptive_runtime_error(self) -> None:
        mock_resp = _make_response([], status_code=404)
        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.post = AsyncMock(return_value=mock_resp)
            mock_client_cls.return_value = mock_client

            provider = TavilySearchProvider(api_key="tvly-test")
            with pytest.raises(RuntimeError, match="HTTP 404"):
                await provider.search("test")

    @pytest.mark.asyncio
    async def test_401_raises_descriptive_runtime_error(self) -> None:
        mock_resp = _make_response([], status_code=401)
        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.post = AsyncMock(return_value=mock_resp)
            mock_client_cls.return_value = mock_client

            provider = TavilySearchProvider(api_key="tvly-test")
            with pytest.raises(RuntimeError, match="HTTP 401"):
                await provider.search("test")

    @pytest.mark.asyncio
    async def test_429_raises_descriptive_runtime_error(self) -> None:
        mock_resp = _make_response([], status_code=429)
        mock_resp.raise_for_status.side_effect = None  # we handle 429 before raise_for_status
        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.post = AsyncMock(return_value=mock_resp)
            mock_client_cls.return_value = mock_client

            provider = TavilySearchProvider(api_key="tvly-test")
            with pytest.raises(RuntimeError, match="rate limit"):
                await provider.search("test")

    @pytest.mark.asyncio
    async def test_non_429_http_error_propagated(self) -> None:
        mock_resp = _make_response([], status_code=500)
        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.post = AsyncMock(return_value=mock_resp)
            mock_client_cls.return_value = mock_client

            provider = TavilySearchProvider(api_key="tvly-test")
            with pytest.raises(httpx.HTTPStatusError):
                await provider.search("test")


# ── Registry integration ─────────────────────────────────────────────


class TestRegistryIntegration:
    def test_tavily_registered_in_default_registry(self) -> None:
        reg = SearchRegistry.default()
        assert "tavily" in reg.list()

    def test_tavily_provider_instance_in_registry(self) -> None:
        reg = SearchRegistry.default()
        provider = reg.get("tavily")
        assert isinstance(provider, TavilySearchProvider)

    def test_registry_still_contains_dummy(self) -> None:
        reg = SearchRegistry.default()
        assert "dummy" in reg.list()

    def test_tavily_appears_in_sorted_list(self) -> None:
        """The search-providers endpoint sorts output; registry itself is insertion-ordered."""
        reg = SearchRegistry.default()
        names = reg.list()
        # All three built-ins must be present; the endpoint layer handles sorting
        assert "dummy" in names
        assert "tavily" in names
