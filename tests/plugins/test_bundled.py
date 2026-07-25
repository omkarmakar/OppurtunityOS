"""Tests for all 9 bundled finder plugins."""

from __future__ import annotations

import importlib
from typing import Any

import pytest

from plugins.base import BasePlugin
from plugins.bundled import ALL_BUNDLED_PLUGINS
from services.search.provider import SearchProvider

# ── Dynamically collect all bundled plugin classes ───────────────────────

PLUGIN_META: list[dict[str, Any]] = []
for cls in ALL_BUNDLED_PLUGINS:
    mod = importlib.import_module(cls.__module__)
    # Find the SearchProvider class defined in the plugin module itself
    # (skip imported base classes like BundledSearchProvider)
    search_cls = None
    module_name = mod.__name__
    for obj in vars(mod).values():
        if (
            isinstance(obj, type)
            and issubclass(obj, SearchProvider)
            and getattr(obj, "__module__", "") == module_name
        ):
            search_cls = obj
            break
    PLUGIN_META.append({
        "plugin_cls": cls,
        "search_cls": search_cls,
        "module": mod,
        "name": cls.plugin_name,
    })


class TestBundledPluginMetadata:
    """Verify each plugin declares proper metadata."""

    @pytest.mark.parametrize("meta", PLUGIN_META, ids=[m["name"] for m in PLUGIN_META])
    def test_plugin_has_metadata(self, meta: dict[str, Any]) -> None:
        cls = meta["plugin_cls"]
        assert cls.plugin_name, f"{cls.__name__} missing plugin_name"
        assert cls.plugin_version, f"{cls.__name__} missing plugin_version"
        assert cls.plugin_description, f"{cls.__name__} missing plugin_description"
        assert cls.plugin_author, f"{cls.__name__} missing plugin_author"

    @pytest.mark.parametrize("meta", PLUGIN_META, ids=[m["name"] for m in PLUGIN_META])
    def test_plugin_is_baseplugin_subclass(self, meta: dict[str, Any]) -> None:
        assert issubclass(meta["plugin_cls"], BasePlugin)

    @pytest.mark.parametrize("meta", PLUGIN_META, ids=[m["name"] for m in PLUGIN_META])
    def test_plugin_is_instantiable(self, meta: dict[str, Any]) -> None:
        instance = meta["plugin_cls"]()
        assert isinstance(instance, BasePlugin)

    @pytest.mark.parametrize("meta", PLUGIN_META, ids=[m["name"] for m in PLUGIN_META])
    def test_plugin_registers_search_provider(self, meta: dict[str, Any]) -> None:
        instance = meta["plugin_cls"]()
        providers = instance.get_search_providers()
        assert len(providers) == 1
        assert issubclass(providers[0], SearchProvider)


class TestBundledSearchProviders:
    """Verify each plugin's SearchProvider works correctly."""

    @pytest.mark.parametrize("meta", PLUGIN_META, ids=[m["name"] for m in PLUGIN_META])
    def test_search_provider_has_name(self, meta: dict[str, Any]) -> None:
        cls = meta["search_cls"]
        instance = cls()
        name = instance.name
        assert name, f"{cls.__name__} has empty name"
        assert isinstance(name, str)

    @pytest.mark.parametrize("meta", PLUGIN_META, ids=[m["name"] for m in PLUGIN_META])
    @pytest.mark.asyncio
    async def test_search_returns_results(self, meta: dict[str, Any]) -> None:
        from services.search.dummy_provider import DummyProvider

        cls = meta["search_cls"]
        instance = cls(inner=DummyProvider())
        results = await instance.search("python developer", count=5)
        assert len(results) <= 5
        for r in results:
            assert hasattr(r, "title")
            assert hasattr(r, "url")
            assert hasattr(r, "snippet")

    @pytest.mark.parametrize("meta", PLUGIN_META, ids=[m["name"] for m in PLUGIN_META])
    @pytest.mark.asyncio
    async def test_search_sets_correct_source(self, meta: dict[str, Any]) -> None:
        """The source field on results should match the domain."""
        from services.search.dummy_provider import DummyProvider

        cls = meta["search_cls"]
        instance = cls(inner=DummyProvider())
        results = await instance.search("test query")
        if results:
            expected = meta["search_cls"]._domain or instance.name.lower()
            assert all(r.source == expected for r in results)

    @pytest.mark.parametrize("meta", PLUGIN_META, ids=[m["name"] for m in PLUGIN_META])
    @pytest.mark.asyncio
    async def test_search_respects_count(self, meta: dict[str, Any]) -> None:
        from services.search.dummy_provider import DummyProvider

        cls = meta["search_cls"]
        instance = cls(inner=DummyProvider())
        results = await instance.search("test", count=3)
        assert len(results) <= 3

    @pytest.mark.parametrize("meta", PLUGIN_META, ids=[m["name"] for m in PLUGIN_META])
    def test_domain_keywords_are_defined(self, meta: dict[str, Any]) -> None:
        cls = meta["search_cls"]
        assert cls._domain, f"{cls.__name__} has empty _domain"
        assert cls._keywords, f"{cls.__name__} has empty _keywords"

    @pytest.mark.parametrize("meta", PLUGIN_META, ids=[m["name"] for m in PLUGIN_META])
    @pytest.mark.asyncio
    async def test_enhance_query_appends_keywords(self, meta: dict[str, Any]) -> None:
        from services.search.dummy_provider import DummyProvider

        cls = meta["search_cls"]
        instance = cls(inner=DummyProvider())
        enhanced = instance._enhance_query("machine learning")
        assert "machine learning" in enhanced
        for kw in cls._keywords:
            assert kw in enhanced


class TestPluginDiscovery:
    """Verify plugins are discoverable via entry points."""

    def test_all_bundled_listed_in_entry_points(self) -> None:
        """Check that ALL_BUNDLED_PLUGINS matches the count (9)."""
        assert len(ALL_BUNDLED_PLUGINS) == 9

    def test_each_plugin_is_unique(self) -> None:
        names = [p.plugin_name for p in ALL_BUNDLED_PLUGINS]
        assert len(names) == len(set(names))

    def test_entry_points_loaded_properly(self) -> None:
        """Verify each entry point resolves to the correct plugin class."""
        import importlib.metadata

        eps = list(importlib.metadata.entry_points(group="opportunityos.plugins"))
        if not eps:
            pytest.skip("Entry points not registered (run 'pip install -e .')")
        loaded = {}
        for ep in eps:
            loaded[ep.name] = ep.load()
        for cls in ALL_BUNDLED_PLUGINS:
            assert (
                loaded.get(cls.plugin_name) is cls
            ), f"{cls.plugin_name} not found or mismatched in entry points"

    def test_bundled_module_imports_all(self) -> None:
        """Verify every plugin class is reachable from its module."""
        for cls in ALL_BUNDLED_PLUGINS:
            mod = importlib.import_module(f"plugins.bundled.{cls.plugin_name}")
            assert hasattr(mod, cls.__name__)
