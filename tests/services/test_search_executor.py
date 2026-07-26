"""Tests for SearchExecutor — verifies Search row creation per query."""

from __future__ import annotations

from unittest.mock import patch
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from database.models.profiles import Profile
from database.models.searches import Search
from database.repositories.search_repository import SearchRepository
from services.search_pipeline.steps.search_executor import SearchExecutor


class TestSearchExecutorRowCreation:
    @pytest.mark.asyncio
    async def test_creates_search_row_per_query(self, db_session: Session) -> None:
        profile = Profile(id=uuid4(), user_id=uuid4())
        step = SearchExecutor(provider_name="dummy", result_count=5)
        ctx = {
            "queries": ["python developer", "fastapi jobs"],
            "profile": profile,
            "db": db_session,
        }
        await step.execute(ctx)

        repo = SearchRepository(db_session)
        rows = repo.list(user_id=profile.user_id)
        assert len(rows) == 2

        queries_found = [r.query for r in rows]
        assert "python developer" in queries_found
        assert "fastapi jobs" in queries_found

    @pytest.mark.asyncio
    async def test_result_count_per_query(self, db_session: Session) -> None:
        profile = Profile(id=uuid4(), user_id=uuid4())
        step = SearchExecutor(provider_name="dummy", result_count=3)
        ctx = {
            "queries": ["test query"],
            "profile": profile,
            "db": db_session,
        }
        await step.execute(ctx)

        repo = SearchRepository(db_session)
        rows = repo.list(user_id=profile.user_id)
        assert len(rows) == 1
        assert rows[0].result_count > 0
        assert rows[0].query == "test query"

    @pytest.mark.asyncio
    async def test_failed_query_creates_row_with_zero_count(self, db_session: Session) -> None:
        profile = Profile(id=uuid4(), user_id=uuid4())
        step = SearchExecutor(provider_name="dummy", result_count=3)
        ctx = {
            "queries": ["good query", "bad query"],
            "profile": profile,
            "db": db_session,
        }

        original_search = step._registry.get("dummy").search

        async def failing_search(query: str, **kwargs):
            if "bad" in query:
                raise RuntimeError("Search provider unavailable")
            return await original_search(query, **kwargs)

        with patch.object(step._registry.get("dummy"), "search", failing_search):
            await step.execute(ctx)

        repo = SearchRepository(db_session)
        rows = repo.list(user_id=profile.user_id)
        assert len(rows) == 2

        good = next(r for r in rows if r.query == "good query")
        bad = next(r for r in rows if r.query == "bad query")

        assert good.result_count > 0
        assert bad.result_count == 0

    @pytest.mark.asyncio
    async def test_row_count_equals_query_count(self, db_session: Session) -> None:
        profile = Profile(id=uuid4(), user_id=uuid4())
        step = SearchExecutor(provider_name="dummy", result_count=3)
        queries = [f"query {i}" for i in range(5)]
        ctx = {
            "queries": queries,
            "profile": profile,
            "db": db_session,
        }
        await step.execute(ctx)

        repo = SearchRepository(db_session)
        rows = repo.list(user_id=profile.user_id)
        assert len(rows) == len(queries)

    @pytest.mark.asyncio
    async def test_empty_queries_no_rows(self, db_session: Session) -> None:
        profile = Profile(id=uuid4(), user_id=uuid4())
        step = SearchExecutor(provider_name="dummy")
        ctx = {
            "queries": [],
            "profile": profile,
            "db": db_session,
        }
        await step.execute(ctx)

        repo = SearchRepository(db_session)
        rows = repo.list(user_id=profile.user_id)
        assert len(rows) == 0
