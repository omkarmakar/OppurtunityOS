"""Tests for the query cache layer."""

from __future__ import annotations

import threading
import time

from services.cache import QueryCache


class TestQueryCache:
    def test_get_set(self):
        cache = QueryCache(ttl=60)
        cache.set("k", "v")
        assert cache.get("k") == "v"

    def test_get_miss(self):
        cache = QueryCache(ttl=60)
        assert cache.get("nonexistent") is None

    def test_get_or_set(self):
        cache = QueryCache(ttl=60)
        called = 0
        def factory() -> int:
            nonlocal called
            called += 1
            return 42
        assert cache.get_or_set("k", factory) == 42
        assert called == 1
        assert cache.get_or_set("k", factory) == 42
        assert called == 1

    def test_expiry(self):
        cache = QueryCache(ttl=0.1)
        cache.set("k", "v")
        assert cache.get("k") == "v"
        time.sleep(0.15)
        assert cache.get("k") is None

    def test_invalidate(self):
        cache = QueryCache(ttl=60)
        cache.set("a", "1")
        cache.set("b", "2")
        cache.invalidate("a")
        assert cache.get("a") is None
        assert cache.get("b") == "2"

    def test_invalidate_pattern(self):
        cache = QueryCache(ttl=60)
        cache.set("user:1", "a")
        cache.set("user:2", "b")
        cache.set("other", "c")
        cache.invalidate_pattern("user:")
        assert cache.get("user:1") is None
        assert cache.get("user:2") is None
        assert cache.get("other") == "c"

    def test_max_size_eviction(self):
        cache = QueryCache(ttl=60, max_size=3)
        cache.set("a", "1")
        cache.set("b", "2")
        cache.set("c", "3")
        cache.set("d", "4")
        assert cache.size <= 3
        assert cache.get("a") is None

    def test_thread_safety(self):
        cache = QueryCache(ttl=60)
        errors = []
        def worker():
            try:
                for i in range(100):
                    cache.set(f"k{i}", i)
                    cache.get(f"k{i}")
            except Exception as e:
                errors.append(e)
        threads = [threading.Thread(target=worker) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert not errors

    def test_clear(self):
        cache = QueryCache(ttl=60)
        cache.set("a", "1")
        cache.set("b", "2")
        cache.clear()
        assert cache.size == 0
