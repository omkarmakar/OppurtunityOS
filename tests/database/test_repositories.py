"""Tests for the repository layer — BaseRepository and concrete repos."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy.orm import Session

from database.base import Base
from database.models import Opportunity, Profile, Source, User
from database.repositories import (
    BaseRepository,
    OpportunityRepository,
    ProfileRepository,
    SourceRepository,
    UserRepository,
)
from database.session import SessionLocal, init_db


@pytest.fixture(autouse=True)
def _db_tables(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    init_db(data_dir=str(db_path.parent))
    yield
    Base.metadata.drop_all(bind=SessionLocal.kw["bind"])


@pytest.fixture
def session() -> Session:
    s = SessionLocal()
    try:
        yield s
    finally:
        s.close()


@pytest.fixture
def user_repo(session: Session) -> UserRepository:
    return UserRepository(session)


@pytest.fixture
def source_repo(session: Session) -> SourceRepository:
    return SourceRepository(session)


@pytest.fixture
def opp_repo(session: Session) -> OpportunityRepository:
    return OpportunityRepository(session)


@pytest.fixture
def existing_user(session: Session) -> User:
    u = User(email="repo_test@example.com", password_hash="pw")
    session.add(u)
    session.commit()
    return u


# ═══════════════════════════════════════════════════════════════════════
#  BaseRepository — generic operations
# ═══════════════════════════════════════════════════════════════════════


class TestBaseRepository:
    """Verify the generic CRUD operations work for every concrete repo."""

    def test_add_and_get(self, user_repo: UserRepository, existing_user: User) -> None:
        # existing_user is already persisted, test get
        fetched = user_repo.get(existing_user.id)
        assert fetched is not None
        assert fetched.email == "repo_test@example.com"

    def test_get_nonexistent_returns_none(self, user_repo: UserRepository) -> None:
        from uuid import uuid4
        assert user_repo.get(uuid4()) is None

    def test_add_new_entity(self, user_repo: UserRepository) -> None:
        u = User(email="new_guy@example.com", password_hash="pw")
        added = user_repo.add(u)
        assert added.id is not None
        # reload
        fetched = user_repo.get(added.id)
        assert fetched is not None

    def test_update_entity(self, user_repo: UserRepository, existing_user: User) -> None:
        existing_user.is_verified = True
        user_repo.update(existing_user)
        fetched = user_repo.get(existing_user.id)
        assert fetched is not None
        assert fetched.is_verified is True

    def test_delete_entity(self, user_repo: UserRepository, existing_user: User) -> None:
        user_repo.delete(existing_user)
        assert user_repo.get(existing_user.id) is None

    def test_list_all(self, user_repo: UserRepository, existing_user: User) -> None:
        users = user_repo.list()
        assert len(users) >= 1  # at least the fixture user

    def test_list_with_filter(self, user_repo: UserRepository, existing_user: User) -> None:
        results = user_repo.list(email="repo_test@example.com")
        assert len(results) == 1
        assert results[0].id == existing_user.id

    def test_list_filter_no_match(self, user_repo: UserRepository) -> None:
        assert user_repo.list(email="nobody@example.com") == []

    def test_count(self, user_repo: UserRepository, existing_user: User) -> None:
        cnt = user_repo.count()
        assert cnt >= 1

    def test_count_with_filter(self, user_repo: UserRepository, existing_user: User) -> None:
        cnt = user_repo.count(is_verified=False)
        assert cnt >= 1

    def test_exists_true(self, user_repo: UserRepository, existing_user: User) -> None:
        assert user_repo.exists(existing_user.id) is True

    def test_exists_false(self, user_repo: UserRepository) -> None:
        from uuid import uuid4
        assert user_repo.exists(uuid4()) is False


# ═══════════════════════════════════════════════════════════════════════
#  Concrete repository — relationship queries
# ═══════════════════════════════════════════════════════════════════════


class TestUserRepository:
    def test_user_with_profile(self, session: Session, existing_user: User) -> None:
        profile = Profile(user_id=existing_user.id, display_name="Repo Tester")
        session.add(profile)
        session.commit()

        repo = UserRepository(session)
        user = repo.get(existing_user.id)
        assert user is not None
        assert user.profile is not None
        assert user.profile.display_name == "Repo Tester"

    def test_user_with_sources(self, session: Session, existing_user: User) -> None:
        session.add(Source(
            user_id=existing_user.id, name="Src1", source_type="rss", config={},
        ))
        session.add(Source(
            user_id=existing_user.id, name="Src2", source_type="api", config={},
        ))
        session.commit()

        repo = UserRepository(session)
        user = repo.get(existing_user.id)
        assert len(user.sources) == 2


class TestOpportunityRepository:
    def test_list_by_status(self, session: Session, existing_user: User) -> None:
        now = datetime.now(timezone.utc)
        session.add_all([
            Opportunity(user_id=existing_user.id, title="A", status="new",
                        discovered_at=now),
            Opportunity(user_id=existing_user.id, title="B", status="applied",
                        discovered_at=now),
            Opportunity(user_id=existing_user.id, title="C", status="new",
                        discovered_at=now),
        ])
        session.commit()

        repo = OpportunityRepository(session)
        new_opps = repo.list(status="new")
        assert len(new_opps) == 2

    def test_count_by_priority(self, session: Session, existing_user: User) -> None:
        now = datetime.now(timezone.utc)
        session.add_all([
            Opportunity(user_id=existing_user.id, title="H", priority="high",
                        discovered_at=now),
            Opportunity(user_id=existing_user.id, title="M1", priority="medium",
                        discovered_at=now),
            Opportunity(user_id=existing_user.id, title="M2", priority="medium",
                        discovered_at=now),
        ])
        session.commit()

        repo = OpportunityRepository(session)
        assert repo.count(priority="high") == 1
        assert repo.count(priority="medium") == 2
