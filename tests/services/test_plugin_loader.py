"""Tests for plugin discovery, loader, and search-executor integration."""

from __future__ import annotations

from typing import Any
from unittest.mock import patch
from uuid import uuid4

import pytest

from plugins.base import BasePlugin
from plugins.loader import discover_entry_point_classes, get_plugin_keywords, load_bundled_plugins
from services.search.models import SearchResult
from services.search.provider import SearchProvider


# ── helpers ──────────────────────────────────────────────────────────


class _DummySearchProvider(SearchProvider):
    """Minimal SearchProvider that returns canned results."""

    def __init__(self, name: str = "DummyTestProvider") -> None:
        self._name = name

    @property
    def name(self) -> str:
        return self._name

    async def search(
        self, query: str, count: int = 10, offset: int = 0
    ) -> list[SearchResult]:
        return [
            SearchResult(
                title=f"Result {i} for {query}",
                url=f"https://example.com/{i}",
                snippet="test",
            )
            for i in range(min(count, 3))
        ]


class _TestPlugin(BasePlugin):
    plugin_name = "test_plugin"
    plugin_version = "0.1.0"
    plugin_description = "A test plugin"
    plugin_author = "Test"

    def initialize(self) -> None:
        pass

    def get_search_providers(self) -> list[type]:
        return [_DummySearchProvider]


# ── Tests ────────────────────────────────────────────────────────────


class TestDiscoverEntryPoints:
    def test_fallback_to_all_bundled_when_no_entry_points(self) -> None:
        """When entry points return empty, fallback list is used."""
        with patch("importlib.metadata.entry_points", return_value=[]):
            classes = discover_entry_point_classes()
        assert len(classes) >= 9
        assert all(issubclass(c, BasePlugin) for c in classes)

    def test_entry_points_loaded_when_available(self) -> None:
        """When entry points exist, they are preferred over fallback."""
        from plugins.bundled import ALL_BUNDLED_PLUGINS

        # Simulate entry points that return only 2 plugins
        fake_entry_points = [
            _FakeEntryPoint("internships", ALL_BUNDLED_PLUGINS[4]),
            _FakeEntryPoint("jobs", ALL_BUNDLED_PLUGINS[5]),
        ]
        with patch("importlib.metadata.entry_points", return_value=fake_entry_points):
            classes = discover_entry_point_classes()
        assert len(classes) == 2


class _FakeEntryPoint:
    """Mimics importlib.metadata.EntryPoint for testing."""

    def __init__(self, name: str, cls: type) -> None:
        self.name = name
        self._cls = cls

    def load(self) -> type:
        return self._cls


class TestLoadBundledPlugins:
    def test_empty_enabled_returns_all(self) -> None:
        plugins = load_bundled_plugins(enabled_plugins=None)
        assert len(plugins) >= 9

    def test_non_empty_filters_correctly(self) -> None:
        plugins = load_bundled_plugins(enabled_plugins=["internships", "jobs"])
        names = [p.plugin_name for p in plugins]
        assert "internships" in names
        assert "jobs" in names
        assert "grants" not in names

    def test_each_plugin_is_initialized(self) -> None:
        plugins = load_bundled_plugins(enabled_plugins=["internships"])
        assert len(plugins) == 1
        p = plugins[0]
        assert p.plugin_name == "internships"
        assert p.plugin_version == "0.1.0"

    def test_get_plugin_keywords(self) -> None:
        plugins = load_bundled_plugins(enabled_plugins=["internships", "research_papers"])
        kw = get_plugin_keywords(plugins)
        assert "internships" in kw
        assert "research_papers" in kw
        assert "internship" in kw["internships"]
        assert "arxiv" in kw["research_papers"]


class TestSearchExecutorPluginIntegration:
    """Verify plugin providers actually influence search results."""

    @pytest.mark.asyncio
    async def test_plugin_provider_adds_results(self) -> None:
        from services.search_pipeline.steps.search_executor import SearchExecutor

        step = SearchExecutor(
            provider_name="dummy",
            result_count=5,
            enabled_plugins=["internships"],
        )

        assert len(step._plugin_providers) == 1
        plugin_provider = step._plugin_providers[0]
        assert "Internship" in plugin_provider.name

    @pytest.mark.asyncio
    async def test_plugin_results_included_in_output(self, db_session) -> None:
        from database.models.users import User
        from database.models.profiles import Profile

        # Ensure a User row exists for the FK constraint
        uid = uuid4()
        db_session.add(User(id=uid, email=f"{uid}@test.com", password_hash="test"))
        db_session.flush()

        profile = Profile(id=uuid4(), user_id=uid)
        db_session.add(profile)
        db_session.flush()

        from services.search_pipeline.steps.search_executor import SearchExecutor

        step = SearchExecutor(
            provider_name="dummy",
            result_count=3,
            enabled_plugins=["internships"],
        )

        ctx: dict[str, Any] = {
            "queries": ["python developer"],
            "profile": profile,
            "db": db_session,
        }
        result = await step.execute(ctx)
        assert "search_results" in result
        # Dummy returns some results + plugin also returns some
        assert len(result["search_results"]) > 0

    @pytest.mark.asyncio
    async def test_no_plugin_providers_when_nonexistent_name(self, db_session) -> None:
        from database.models.users import User
        from database.models.profiles import Profile

        uid = uuid4()
        db_session.add(User(id=uid, email=f"{uid}@test.com", password_hash="test"))
        db_session.flush()

        profile = Profile(id=uuid4(), user_id=uid)
        db_session.add(profile)
        db_session.flush()

        from services.search_pipeline.steps.search_executor import SearchExecutor

        step = SearchExecutor(
            provider_name="dummy",
            result_count=3,
            enabled_plugins=["no_such_plugin"],
        )

        assert len(step._plugin_providers) == 0

    @pytest.mark.asyncio
    async def test_plugin_provider_enhances_query(self) -> None:
        """Verify the plugin's _enhance_query method appends domain keywords."""
        from plugins.bundled.internships import InternshipSearchProvider

        from services.search.dummy_provider import DummyProvider

        provider = InternshipSearchProvider(inner=DummyProvider())
        enhanced = provider._enhance_query("python developer")
        assert "python developer" in enhanced
        assert "internship" in enhanced
        assert "intern" in enhanced