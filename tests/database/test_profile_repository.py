"""Profile repository tests."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy.orm import Session

from database.models.profiles import Profile
from database.models.users import User
from database.repositories.profile_repository import ProfileRepository


def _user(db_session: Session) -> User:
    uid = uuid.uuid4()
    u = User(id=uid, email=f"{uid}@test.com", password_hash="test-hash")
    db_session.add(u)
    db_session.commit()
    return u


class TestProfileRepository:
    def test_get_by_user_id_returns_first_profile(self, db_session: Session) -> None:
        u = _user(db_session)
        p1 = Profile(user_id=u.id, name="First")
        p2 = Profile(user_id=u.id, name="Second")
        db_session.add_all([p1, p2])
        db_session.commit()

        repo = ProfileRepository(db_session)
        result = repo.get_by_user_id(u.id)
        assert result is not None
        assert result.name == "First"

    def test_list_by_user_id_returns_all_profiles(self, db_session: Session) -> None:
        u = _user(db_session)
        p1 = Profile(user_id=u.id, name="Profile 1")
        p2 = Profile(user_id=u.id, name="Profile 2")
        db_session.add_all([p1, p2])
        db_session.commit()

        repo = ProfileRepository(db_session)
        results = repo.list_by_user_id(u.id)
        assert len(results) == 2
        names = [p.name for p in results]
        assert "Profile 1" in names
        assert "Profile 2" in names

    def test_count_by_user_id(self, db_session: Session) -> None:
        u = _user(db_session)
        db_session.add_all([
            Profile(user_id=u.id, name="P1"),
            Profile(user_id=u.id, name="P2"),
        ])
        db_session.commit()

        repo = ProfileRepository(db_session)
        assert repo.count_by_user_id(u.id) == 2
        assert repo.count_by_user_id(uuid.uuid4()) == 0

    def test_upsert_creates_new_profile(self, db_session: Session) -> None:
        u = _user(db_session)
        profile = Profile(user_id=u.id, name="New Profile", bio="Test bio")

        repo = ProfileRepository(db_session)
        result = repo.upsert(profile)
        db_session.commit()

        assert result.id is not None
        assert result.bio == "Test bio"

    def test_upsert_updates_existing_profile(self, db_session: Session) -> None:
        u = _user(db_session)
        existing = Profile(user_id=u.id, name="Old Name", bio="Old bio")
        db_session.add(existing)
        db_session.commit()

        updated = Profile(user_id=u.id, name="New Name", bio="New bio")
        repo = ProfileRepository(db_session)
        result = repo.upsert(updated)
        db_session.commit()

        assert result.id == existing.id
        assert result.name == "New Name"
        assert result.bio == "New bio"