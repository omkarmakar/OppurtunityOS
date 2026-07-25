"""Tests for the ChromaDB memory service."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from core.config import MemorySettings
from services.memory import ChromaMemoryStore, MemoryEntry, MemoryQuery, MemoryResult, MemoryService, MemoryType


@pytest.fixture
def memory_settings() -> MemorySettings:
    return MemorySettings(
        enabled=True,
        persist_directory="",  # in-memory
        collection_name="test_memory",
        top_k=10,
    )


@pytest.fixture
def store(memory_settings: MemorySettings) -> ChromaMemoryStore:
    s = ChromaMemoryStore(memory_settings)
    s.initialize()
    yield s
    s.close()


@pytest.fixture
def sample_entries() -> list[MemoryEntry]:
    ts = datetime.now(timezone.utc).isoformat()
    return [
        MemoryEntry(
            id=str(uuid.uuid4()),
            type=MemoryType.SEARCH,
            user_id="user-a",
            content="Searched for machine learning engineer jobs",
            title="Searched: ML engineer",
            metadata_={"query": "machine learning engineer", "result_count": 15},
            created_at=ts,
        ),
        MemoryEntry(
            id=str(uuid.uuid4()),
            type=MemoryType.SEARCH,
            user_id="user-a",
            content="Searched for python developer internships",
            title="Searched: python intern",
            metadata_={"query": "python developer", "result_count": 8},
            created_at=ts,
        ),
        MemoryEntry(
            id=str(uuid.uuid4()),
            type=MemoryType.BOOKMARK,
            user_id="user-a",
            content="Bookmarked: Senior ML Engineer at Google",
            title="Bookmark: Google ML Engineer",
            metadata_={"opportunity_id": str(uuid.uuid4()), "url": "https://careers.google.com/xyz"},
            created_at=ts,
        ),
        MemoryEntry(
            id=str(uuid.uuid4()),
            type=MemoryType.REJECTED,
            user_id="user-a",
            content="Rejected: Junior Developer at Acme Corp — Reason: low salary",
            title="Rejected: Acme Junior Dev",
            metadata_={"opportunity_id": str(uuid.uuid4()), "reason": "low salary"},
            created_at=ts,
        ),
        MemoryEntry(
            id=str(uuid.uuid4()),
            type=MemoryType.FEEDBACK,
            user_id="user-b",
            content="Feedback on opportunity: rating=5 — Great role!",
            title="Rating 5/5",
            metadata_={"opportunity_id": str(uuid.uuid4()), "rating": 5, "comment": "Great role!"},
            created_at=ts,
        ),
    ]


# ── ChromaMemoryStore tests ────────────────────────────────────────────


class TestChromaMemoryStore:
    def test_initialize_and_close(self, memory_settings: MemorySettings) -> None:
        s = ChromaMemoryStore(memory_settings)
        assert not s.is_initialized
        s.initialize()
        assert s.is_initialized
        s.close()
        assert not s.is_initialized

    def test_store_and_count(self, store: ChromaMemoryStore) -> None:
        entry = MemoryEntry(
            id=str(uuid.uuid4()),
            type=MemoryType.SEARCH,
            user_id="user-a",
            content="Test search",
        )
        store.store(entry)
        assert store.count() >= 1
        assert store.count(user_id="user-a") >= 1

    def test_store_batch(self, store: ChromaMemoryStore, sample_entries: list[MemoryEntry]) -> None:
        store.store_batch(sample_entries)
        assert store.count() >= len(sample_entries)

    def test_search_returns_results(self, store: ChromaMemoryStore, sample_entries: list[MemoryEntry]) -> None:
        store.store_batch(sample_entries)
        results = store.search(MemoryQuery(text="machine learning", top_k=5))
        assert len(results) > 0
        for r in results:
            assert isinstance(r, MemoryResult)
            assert r.id
            assert r.type
            assert r.user_id

    def test_search_filters_by_user(self, store: ChromaMemoryStore, sample_entries: list[MemoryEntry]) -> None:
        store.store_batch(sample_entries)
        results = store.search(MemoryQuery(text="search", user_id="user-a", top_k=10))
        assert all(r.user_id == "user-a" for r in results)

    def test_search_filters_by_type(self, store: ChromaMemoryStore, sample_entries: list[MemoryEntry]) -> None:
        store.store_batch(sample_entries)
        results = store.search(MemoryQuery(text="", type=MemoryType.BOOKMARK, top_k=10))
        assert all(r.type == "bookmark" for r in results)

    def test_search_empty_returns_empty_list(self, store: ChromaMemoryStore) -> None:
        results = store.search(MemoryQuery(text="nonexistent content", top_k=5))
        assert isinstance(results, list)

    def test_get_recent(self, store: ChromaMemoryStore, sample_entries: list[MemoryEntry]) -> None:
        store.store_batch(sample_entries)
        results = store.get_recent("user-a", limit=10)
        assert len(results) >= 2
        assert all(r.user_id == "user-a" for r in results)

    def test_get_by_type(self, store: ChromaMemoryStore, sample_entries: list[MemoryEntry]) -> None:
        store.store_batch(sample_entries)
        results = store.get_by_type("user-a", MemoryType.SEARCH, limit=10)
        assert len(results) >= 1
        assert all(r.type == "search" for r in results)

    def test_delete(self, store: ChromaMemoryStore) -> None:
        entry_id = str(uuid.uuid4())
        entry = MemoryEntry(id=entry_id, type=MemoryType.SEARCH, user_id="user-a", content="to delete")
        store.store(entry)
        assert store.count() >= 1
        store.delete(entry_id)
        # After delete we can only check that search doesn't return it
        results = store.search(MemoryQuery(text="to delete", top_k=5))
        assert not any(r.id == entry_id for r in results)

    def test_delete_by_user(self, store: ChromaMemoryStore, sample_entries: list[MemoryEntry]) -> None:
        store.store_batch(sample_entries)
        store.delete_by_user("user-b")
        results = store.get_recent("user-b", limit=10)
        assert len(results) == 0
        # user-a entries should remain
        results_a = store.get_recent("user-a", limit=10)
        assert len(results_a) > 0

    def test_raises_if_not_initialized(self, memory_settings: MemorySettings) -> None:
        s = ChromaMemoryStore(memory_settings)
        with pytest.raises(RuntimeError, match="not initialized"):
            s.collection  # noqa: B018


# ── MemoryService tests ────────────────────────────────────────────────


@pytest.fixture
def memory_service(memory_settings: MemorySettings) -> MemoryService:
    from core.config import AppConfig

    config = AppConfig()
    config.memory = memory_settings
    svc = MemoryService(config)
    svc.initialize()
    yield svc
    svc.close()


class TestMemoryService:
    def test_store_search(self, memory_service: MemoryService) -> None:
        entry_id = memory_service.store_search("user-a", "machine learning jobs", 10)
        assert entry_id
        results = memory_service.recall("machine learning", user_id="user-a")
        assert any(r.id == entry_id for r in results)

    def test_store_feedback(self, memory_service: MemoryService) -> None:
        opp_id = str(uuid.uuid4())
        entry_id = memory_service.store_feedback("user-a", opp_id, 4, "Good opportunity")
        assert entry_id
        results = memory_service.recall_by_type("user-a", MemoryType.FEEDBACK)
        assert any(r.id == entry_id for r in results)

    def test_store_bookmark(self, memory_service: MemoryService) -> None:
        opp_id = str(uuid.uuid4())
        entry_id = memory_service.store_bookmark("user-a", opp_id, "ML Engineer at Google", "https://google.com")
        assert entry_id
        results = memory_service.recall_by_type("user-a", MemoryType.BOOKMARK)
        assert any(r.id == entry_id for r in results)

    def test_store_rejected(self, memory_service: MemoryService) -> None:
        opp_id = str(uuid.uuid4())
        entry_id = memory_service.store_rejected("user-a", opp_id, "Junior Dev at Acme", "low salary")
        assert entry_id
        results = memory_service.recall_by_type("user-a", MemoryType.REJECTED)
        assert any(r.id == entry_id for r in results)

    def test_store_prompt(self, memory_service: MemoryService) -> None:
        entry_id = memory_service.store_prompt("user-a", "Find me remote Python jobs")
        assert entry_id
        results = memory_service.recall("Python remote", user_id="user-a")
        assert any(r.id == entry_id for r in results)

    def test_recall_semantic(self, memory_service: MemoryService) -> None:
        memory_service.store_search("user-a", "machine learning researcher", 5)
        memory_service.store_search("user-b", "data scientist", 3)
        results = memory_service.recall("ML research", user_id="user-a")
        assert all(r.user_id == "user-a" for r in results)

    def test_recall_recent(self, memory_service: MemoryService) -> None:
        memory_service.store_search("user-a", "search 1", 0)
        memory_service.store_search("user-a", "search 2", 0)
        memory_service.store_search("user-b", "search 3", 0)
        results = memory_service.recall_recent("user-a", limit=10)
        assert all(r.user_id == "user-a" for r in results)
        assert len(results) >= 2

    def test_recall_by_type(self, memory_service: MemoryService) -> None:
        memory_service.store_search("user-a", "search query", 5)
        memory_service.store_bookmark("user-a", str(uuid.uuid4()), "A bookmarked item")
        results = memory_service.recall_by_type("user-a", MemoryType.SEARCH)
        assert all(r.type == "search" for r in results)

    def test_multiple_users_isolation(self, memory_service: MemoryService) -> None:
        memory_service.store_search("user-a", "python jobs", 5)
        memory_service.store_search("user-b", "java jobs", 3)
        results_a = memory_service.recall("jobs", user_id="user-a")
        results_b = memory_service.recall("jobs", user_id="user-b")
        assert all(r.user_id == "user-a" for r in results_a)
        assert all(r.user_id == "user-b" for r in results_b)

    def test_recall_without_user_returns_all(self, memory_service: MemoryService) -> None:
        memory_service.store_search("user-a", "query a", 1)
        memory_service.store_search("user-b", "query b", 1)
        results = memory_service.recall("query")
        user_ids = {r.user_id for r in results}
        assert "user-a" in user_ids
        assert "user-b" in user_ids


# ── MemorySettings tests ────────────────────────────────────────────────


class TestMemorySettings:
    def test_defaults(self) -> None:
        settings = MemorySettings()
        assert settings.enabled is True
        assert settings.persist_directory == "data/memory"
        assert settings.collection_name == "opportunityos_memory"
        assert settings.top_k == 10

    def test_in_memory_mode(self) -> None:
        settings = MemorySettings(persist_directory="")
        assert settings.persist_directory == ""
