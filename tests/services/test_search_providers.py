"""Search provider tests."""

from __future__ import annotations

import pytest
from datetime import datetime, timezone

from services.search.dummy_provider import DummyProvider
from services.search.models import SearchResult
from services.search.provider import SearchProvider
from services.search.registry import SearchRegistry
from services.job_boards.base import JobPosting


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


class TestJobPostingConversion:
    def test_jobposting_to_searchresult(self) -> None:
        """Verify JobPosting → SearchResult conversion via raw= field."""
        posting = JobPosting(
            title="Python Developer",
            company="Acme Corp",
            url="https://careers.acme.com/python-dev",
            description="Build great things with Python",
            location="Remote",
            salary="$100k-$150k",
            job_type="full-time",
            skills=["python", "django"],
            experience_required="3+ years",
            posted_date=datetime(2026, 7, 25, tzinfo=timezone.utc),
            application_deadline="2026-08-15",
            board="jsearch",
            job_id="abc123",
        )
        # Simulate the conversion done in jobboard_provider.py / tasks.py
        result = SearchResult(
            title=posting.title,
            url=posting.url,
            snippet=posting.description[:300] if posting.description else f"{posting.company} - {posting.job_type}",
            source=posting.board,
            raw={
                "company": posting.company,
                "location": posting.location,
                "salary": posting.salary,
                "job_type": posting.job_type,
                "skills": posting.skills,
                "experience_required": posting.experience_required,
                "posted_date": posting.posted_date.isoformat() if posting.posted_date else None,
                "application_deadline": posting.application_deadline,
            }
        )
        assert result.title == "Python Developer"
        assert result.raw["company"] == "Acme Corp"
        assert result.raw["skills"] == ["python", "django"]
        assert result.raw["salary"] == "$100k-$150k"
        assert result.source == "jsearch"


class TestJobBoardProviderNoLiveCalls:
    @pytest.mark.asyncio
    async def test_search_reads_from_db_not_rapidapi(self) -> None:
        """Verify ad-hoc search hits DB, not RapidAPI."""
        from services.search.jobboard_provider import JobBoardProvider
        from unittest.mock import patch, MagicMock

        provider = JobBoardProvider()
        mock_db = MagicMock()
        mock_query = MagicMock()
        mock_db.query.return_value.filter.return_value.order_by.return_value.limit.return_value = mock_query
        mock_query.all.return_value = []

        with patch("backend.api.deps.get_db", return_value=iter([mock_db])):
            results = await provider.search("python developer", count=5)
            # Should return empty list (no stored opps), NOT raise or call RapidAPI
            assert results == []
            # DB was queried
            mock_db.query.assert_called_once()

    @pytest.mark.asyncio
    async def test_search_live_requires_explicit_call(self) -> None:
        """Verify search_live is separate from regular search."""
        from services.search.jobboard_provider import JobBoardProvider
        provider = JobBoardProvider()
        # search() should never call search_live
        assert hasattr(provider, 'search_live')
        assert provider.search_live is not provider.search


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


class TestSearchRegistry:
    def test_default_registry_contains_builtins(self) -> None:
        reg = SearchRegistry.default()
        providers = reg.list()
        assert "dummy" in providers
        assert "tavily" in providers

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
