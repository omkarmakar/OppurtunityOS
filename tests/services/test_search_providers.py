"""Search provider tests."""

from __future__ import annotations

import pytest

from services.search.brave_provider import BraveSearchProvider
from services.search.dummy_provider import DummyProvider
from services.search.models import SearchResult
from services.search.provider import SearchProvider
from services.search.registry import SearchRegistry


class TestSearchResult:
    def test_default_fields(self) -> None:
        r = SearchResult()
        assert r.title == ""
        assert r.url == ""
        assert r.snippet == ""
        assert r.source == ""

    def test_all_fields(self) -> None:
        r = SearchResult(title="T", url="U", snippet="S", source="P", raw={"key": "val"})
        assert r.title == "T"
        assert r.raw == {"key": "val"}


class TestDummyProvider:
    def test_name(self) -> None:
        assert DummyProvider().name == "Dummy"

    @pytest.mark.asyncio
    async def test_search_returns_results(self) -> None:
        dp = DummyProvider()
        results = await dp.search("test query")
        assert len(results) > 0
        assert all(isinstance(r, SearchResult) for r in results)

    @pytest.mark.asyncio
    async def test_search_respects_count(self) -> None:
        dp = DummyProvider()
        results = await dp.search("test", count=3)
        assert len(results) == 3

    @pytest.mark.asyncio
    async def test_search_titles_contain_query(self) -> None:
        dp = DummyProvider()
        results = await dp.search("python")
        for r in results:
            assert "python" in r.title.lower()

    @pytest.mark.asyncio
    async def test_results_have_source(self) -> None:
        dp = DummyProvider()
        results = await dp.search("test")
        for r in results:
            assert r.source == "Dummy"

    @pytest.mark.asyncio
    async def test_offset_works(self) -> None:
        dp = DummyProvider()
        all_results = await dp.search("test", count=5)
        offset_results = await dp.search("test", count=3, offset=2)
        assert offset_results[0].title == all_results[2].title


class TestBraveSearchProvider:
    def test_name(self) -> None:
        assert BraveSearchProvider().name == "Brave"

    @pytest.mark.asyncio
    async def test_raises_without_api_key(self) -> None:
        bp = BraveSearchProvider(api_key="")
        with pytest.raises(RuntimeError, match="API key"):
            await bp.search("test")


class TestSearchRegistry:
    def test_default_registry_contains_builtins(self) -> None:
        reg = SearchRegistry.default()
        providers = reg.list()
        assert "dummy" in providers
        assert "brave" in providers

    def test_get_known_provider(self) -> None:
        reg = SearchRegistry.default()
        dp = reg.get("dummy")
        assert isinstance(dp, DummyProvider)

    def test_get_unknown_provider_raises(self) -> None:
        reg = SearchRegistry.default()
        with pytest.raises(KeyError):
            reg.get("nonexistent")

    def test_register_custom_provider(self) -> None:
        reg = SearchRegistry()

        class CustomProvider(SearchProvider):
            @property
            def name(self) -> str:
                return "Custom"

            async def search(self, query: str, count: int = 10, offset: int = 0) -> list[SearchResult]:
                return []

        reg.register(CustomProvider())
        assert "custom" in reg.list()
        assert isinstance(reg.get("custom"), CustomProvider)
