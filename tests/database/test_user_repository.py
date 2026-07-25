"""Tests for UserRepository — get_or_create idempotency and edge cases."""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from database.base import Base
from database.models import User
from database.repositories import UserRepository
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
def repo(session: Session) -> UserRepository:
    return UserRepository(session)


# ═══════════════════════════════════════════════════════════════════════
#  get_or_create — core contract
# ═══════════════════════════════════════════════════════════════════════


class TestGetOrCreate:
    def test_creates_new_row_when_absent(self, repo: UserRepository) -> None:
        uid = uuid.uuid4()
        user = repo.get_or_create(uid, email="new@example.com")
        assert user.id == uid
        assert user.email == "new@example.com"

    def test_returns_existing_row_on_second_call(self, repo: UserRepository, session: Session) -> None:
        uid = uuid.uuid4()
        first = repo.get_or_create(uid, email="first@example.com")
        session.commit()
        second = repo.get_or_create(uid, email="different@example.com")
        # Must be the same row — email must NOT change on second call.
        assert second.id == first.id
        assert second.email == "first@example.com"

    def test_idempotent_called_many_times(self, repo: UserRepository, session: Session) -> None:
        uid = uuid.uuid4()
        repo.get_or_create(uid, email="idempotent@example.com")
        session.commit()
        for _ in range(5):
            u = repo.get_or_create(uid)
            assert u.id == uid

    def test_placeholder_email_used_when_no_email_given(self, repo: UserRepository) -> None:
        uid = uuid.uuid4()
        user = repo.get_or_create(uid)
        assert "@no-email.invalid" in user.email

    def test_placeholder_contains_user_id(self, repo: UserRepository) -> None:
        uid = uuid.uuid4()
        user = repo.get_or_create(uid)
        assert str(uid) in user.email

    def test_user_row_is_persisted_after_flush(self, repo: UserRepository, session: Session) -> None:
        uid = uuid.uuid4()
        repo.get_or_create(uid, email="flushed@example.com")
        session.commit()
        fetched = repo.get(uid)
        assert fetched is not None
        assert fetched.email == "flushed@example.com"

    def test_created_user_is_active_by_default(self, repo: UserRepository) -> None:
        user = repo.get_or_create(uuid.uuid4(), email="active@example.com")
        assert user.is_active is True

    def test_two_different_user_ids_create_two_rows(
        self, repo: UserRepository, session: Session
    ) -> None:
        uid_a = uuid.uuid4()
        uid_b = uuid.uuid4()
        repo.get_or_create(uid_a, email="a@example.com")
        repo.get_or_create(uid_b, email="b@example.com")
        session.commit()
        assert repo.count() == 2


# ═══════════════════════════════════════════════════════════════════════
#  get_by_email
# ═══════════════════════════════════════════════════════════════════════


class TestGetByEmail:
    def test_finds_existing_user(self, repo: UserRepository, session: Session) -> None:
        u = User(email="findme@example.com", password_hash="pw")
        session.add(u)
        session.commit()
        found = repo.get_by_email("findme@example.com")
        assert found is not None
        assert found.id == u.id

    def test_returns_none_for_unknown_email(self, repo: UserRepository) -> None:
        assert repo.get_by_email("nobody@example.com") is None


# ═══════════════════════════════════════════════════════════════════════
#  Profile auto-creates user (integration path)
# ═══════════════════════════════════════════════════════════════════════


class TestProfileAutoCreatesUser:
    """Verify that creating a Profile via get_or_create guarantees the FK."""

    def test_profile_can_be_created_after_get_or_create(
        self, repo: UserRepository, session: Session
    ) -> None:
        from database.models import Profile

        uid = uuid.uuid4()
        repo.get_or_create(uid, email="profile-fk@example.com")
        profile = Profile(user_id=uid, display_name="FK Test")
        session.add(profile)
        session.commit()  # must not raise IntegrityError

        session.refresh(profile)
        assert profile.user_id == uid
