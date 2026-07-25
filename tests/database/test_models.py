"""Tests for SQLAlchemy ORM models — table creation, relationships, constraints."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy import inspect
from sqlalchemy.orm import Session

from database.base import Base
from database.models import (
    ApplicationSettings,
    Bookmark,
    Notification,
    Opportunity,
    Profile,
    Search,
    Source,
    User,
)
from database.session import SessionLocal, init_db, engine


@pytest.fixture(autouse=True)
def _db_tables(tmp_path: Path) -> None:
    """Create all tables in a temporary SQLite database before each test.

    Also ensures the default data directory exists for the module-level engine.
    """
    # The engine was created with the config URL (./data/opportunity.db).
    # Ensure that directory exists.
    data_dir = Path.cwd() / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    init_db(data_dir=str(tmp_path / "data"))
    yield
    # Clean up tables after test
    Base.metadata.drop_all(bind=SessionLocal.kw["bind"])
    # Remove the data directory created for the engine
    import shutil
    shutil.rmtree(data_dir, ignore_errors=True)


@pytest.fixture
def session() -> Session:
    """Provide a clean SQLAlchemy session."""
    s = SessionLocal()
    try:
        yield s
    finally:
        s.close()


# ═══════════════════════════════════════════════════════════════════════
#  Table existence & schema
# ═══════════════════════════════════════════════════════════════════════


class TestTableCreation:
    """Verify every table is created with the expected columns."""

    EXPECTED_TABLES: set[str] = {
        "users",
        "profiles",
        "sources",
        "searches",
        "opportunities",
        "bookmarks",
        "notifications",
        "application_settings",
    }

    def test_all_tables_exist(self) -> None:
        inspector = inspect(SessionLocal.kw["bind"])
        existing = set(inspector.get_table_names())
        missing = self.EXPECTED_TABLES - existing
        assert not missing, f"Missing tables: {missing}"

    @pytest.mark.parametrize(
        ("table", "expected_columns"),
        [
            ("users", {"id", "email", "password_hash", "is_active", "is_verified",
                       "last_login_at", "created_at", "updated_at"}),
            ("profiles", {"id", "user_id", "display_name", "avatar_url", "bio",
                          "preferences", "created_at", "updated_at"}),
            ("sources", {"id", "user_id", "name", "source_type", "config",
                         "is_enabled", "last_fetched_at", "created_at", "updated_at"}),
            ("searches", {"id", "user_id", "query", "filters", "is_saved",
                          "last_run_at", "result_count", "created_at", "updated_at"}),
            ("opportunities", {"id", "user_id", "source_id", "title", "description",
                               "url", "source_type", "status", "priority",
                               "metadata", "discovered_at", "created_at", "updated_at"}),
            ("bookmarks", {"id", "user_id", "opportunity_id", "notes", "created_at"}),
            ("notifications", {"id", "user_id", "type", "title", "message",
                               "is_read", "read_at", "created_at"}),
            ("application_settings", {"id", "user_id", "theme", "language",
                                      "notifications_enabled",
                                      "notification_preferences",
                                      "created_at", "updated_at"}),
        ],
    )
    def test_table_columns(self, table: str, expected_columns: set[str]) -> None:
        inspector = inspect(SessionLocal.kw["bind"])
        actual = {c["name"] for c in inspector.get_columns(table)}
        missing = expected_columns - actual
        assert not missing, f"Table {table!r} missing columns: {missing}"


# ═══════════════════════════════════════════════════════════════════════
#  ORM model creation & persistence
# ═══════════════════════════════════════════════════════════════════════


class TestUserModel:
    """User CRUD and relationship integrity."""

    def test_create_user(self, session: Session) -> None:
        user = User(
            email="alice@example.com",
            password_hash="hashed_pw",
        )
        session.add(user)
        session.commit()

        saved = session.get(User, user.id)
        assert saved is not None
        assert saved.email == "alice@example.com"
        assert saved.is_active is True
        assert saved.is_verified is False
        assert isinstance(saved.created_at, datetime)

    def test_email_uniqueness(self, session: Session) -> None:
        session.add(User(email="dup@example.com", password_hash="a"))
        session.commit()

        dup = User(email="dup@example.com", password_hash="b")
        session.add(dup)
        with pytest.raises(Exception):
            session.commit()

    def test_user_profile_relationship(self, session: Session) -> None:
        user = User(email="bob@example.com", password_hash="pw")
        session.add(user)
        session.flush()

        profile = Profile(user_id=user.id, display_name="Bob")
        session.add(profile)
        session.commit()

        assert user.profile is not None
        assert user.profile.display_name == "Bob"
        assert user.profile.user is user

    def test_cascade_delete_user_deletes_profile(self, session: Session) -> None:
        user = User(email="cascade@example.com", password_hash="pw")
        session.add(user)
        session.flush()
        session.add(Profile(user_id=user.id))
        session.commit()

        session.delete(user)
        session.commit()

        profiles = session.query(Profile).all()
        assert len(profiles) == 0


class TestSourceModel:
    def test_create_source(self, session: Session) -> None:
        user = User(email="source_user@example.com", password_hash="pw")
        session.add(user)
        session.flush()

        source = Source(
            user_id=user.id,
            name="RSS Feed",
            source_type="rss",
            config={"url": "https://example.com/feed.xml"},
        )
        session.add(source)
        session.commit()

        saved = session.get(Source, source.id)
        assert saved is not None
        assert saved.config["url"] == "https://example.com/feed.xml"

    def test_user_sources_relationship(self, session: Session) -> None:
        user = User(email="multi_source@example.com", password_hash="pw")
        session.add(user)
        session.flush()

        s1 = Source(user_id=user.id, name="Src1", source_type="manual", config={})
        s2 = Source(user_id=user.id, name="Src2", source_type="api", config={})
        session.add_all([s1, s2])
        session.commit()

        assert len(user.sources) == 2


class TestOpportunityModel:
    def test_create_opportunity(self, session: Session) -> None:
        user = User(email="opp_user@example.com", password_hash="pw")
        session.add(user)
        session.flush()

        opp = Opportunity(
            user_id=user.id,
            title="Software Engineer at Acme",
            description="Great opportunity",
            status="new",
            priority="high",
            discovered_at=datetime.now(timezone.utc),
        )
        session.add(opp)
        session.commit()

        saved = session.get(Opportunity, opp.id)
        assert saved.title == "Software Engineer at Acme"
        assert saved.status == "new"

    def test_opportunity_source_relationship(self, session: Session) -> None:
        user = User(email="opp_src@example.com", password_hash="pw")
        session.add(user)
        session.flush()

        source = Source(user_id=user.id, name="Jobs API", source_type="api", config={})
        session.add(source)
        session.flush()

        opp = Opportunity(
            user_id=user.id,
            source_id=source.id,
            title="Engineer",
            discovered_at=datetime.now(timezone.utc),
        )
        session.add(opp)
        session.commit()

        assert opp.source is source
        assert opp.source.name == "Jobs API"


class TestBookmarkModel:
    def test_create_bookmark(self, session: Session) -> None:
        user = User(email="bm_user@example.com", password_hash="pw")
        session.add(user)
        session.flush()

        opp = Opportunity(
            user_id=user.id,
            title="Bookmarked Opp",
            discovered_at=datetime.now(timezone.utc),
        )
        session.add(opp)
        session.flush()

        bm = Bookmark(user_id=user.id, opportunity_id=opp.id, notes="Looks promising")
        session.add(bm)
        session.commit()

        assert bm.opportunity is opp

    def test_unique_constraint(self, session: Session) -> None:
        user = User(email="bm_uniq@example.com", password_hash="pw")
        session.add(user)
        session.flush()
        opp = Opportunity(
            user_id=user.id,
            title="Unique Opp",
            discovered_at=datetime.now(timezone.utc),
        )
        session.add(opp)
        session.flush()

        session.add(Bookmark(user_id=user.id, opportunity_id=opp.id))
        session.commit()

        dup = Bookmark(user_id=user.id, opportunity_id=opp.id)
        session.add(dup)
        with pytest.raises(Exception):
            session.commit()


class TestNotificationModel:
    def test_create_notification(self, session: Session) -> None:
        user = User(email="notif_user@example.com", password_hash="pw")
        session.add(user)
        session.flush()

        notif = Notification(
            user_id=user.id,
            type_="info",
            title="Welcome!",
            message="Thanks for joining",
        )
        session.add(notif)
        session.commit()

        assert notif.is_read is False
        assert notif.title == "Welcome!"


class TestApplicationSettingsModel:
    def test_create_settings(self, session: Session) -> None:
        user = User(email="settings_user@example.com", password_hash="pw")
        session.add(user)
        session.flush()

        settings = ApplicationSettings(
            user_id=user.id,
            theme="dark",
            language="fr",
        )
        session.add(settings)
        session.commit()

        assert settings.theme == "dark"
        assert settings.language == "fr"
        assert settings.notifications_enabled is True

    def test_user_settings_one_to_one(self, session: Session) -> None:
        user = User(email="one2one@example.com", password_hash="pw")
        session.add(user)
        session.flush()

        s1 = ApplicationSettings(user_id=user.id)
        session.add(s1)
        session.commit()

        s2 = ApplicationSettings(user_id=user.id)
        session.add(s2)
        with pytest.raises(Exception):
            session.commit()


# ═══════════════════════════════════════════════════════════════════════
#  Timestamp defaults
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize(
    "model_cls",
    [User, Profile, Source, Search, Opportunity, Bookmark, Notification, ApplicationSettings],
)
def test_timestamps_set_on_create(model_cls, session: Session) -> None:
    """Every model with created_at should have it populated on insert."""
    # Build minimal instance
    kwargs: dict = {}
    if model_cls is User:
        kwargs["email"] = "ts@example.com"
        kwargs["password_hash"] = "pw"
    elif model_cls is Profile:
        u = User(email="ts_profile@example.com", password_hash="pw")
        session.add(u)
        session.flush()
        kwargs["user_id"] = u.id
    elif model_cls is Source:
        u = User(email="ts_source@example.com", password_hash="pw")
        session.add(u)
        session.flush()
        kwargs["user_id"] = u.id
        kwargs["name"] = "Test"
        kwargs["source_type"] = "rss"
        kwargs["config"] = {}
    elif model_cls is Search:
        u = User(email="ts_search@example.com", password_hash="pw")
        session.add(u)
        session.flush()
        kwargs["user_id"] = u.id
        kwargs["query"] = "test"
    elif model_cls is Opportunity:
        u = User(email="ts_opp@example.com", password_hash="pw")
        session.add(u)
        session.flush()
        kwargs["user_id"] = u.id
        kwargs["title"] = "Test"
        kwargs["discovered_at"] = datetime.now(timezone.utc)
    elif model_cls is Bookmark:
        u = User(email="ts_bm@example.com", password_hash="pw")
        session.add(u)
        session.flush()
        o = Opportunity(
            user_id=u.id, title="Test", discovered_at=datetime.now(timezone.utc),
        )
        session.add(o)
        session.flush()
        kwargs["user_id"] = u.id
        kwargs["opportunity_id"] = o.id
    elif model_cls is Notification:
        u = User(email="ts_notif@example.com", password_hash="pw")
        session.add(u)
        session.flush()
        kwargs["user_id"] = u.id
        kwargs["type_"] = "info"
        kwargs["title"] = "Test"
    elif model_cls is ApplicationSettings:
        u = User(email="ts_as@example.com", password_hash="pw")
        session.add(u)
        session.flush()
        kwargs["user_id"] = u.id

    instance = model_cls(**kwargs)
    session.add(instance)
    session.commit()

    assert instance.created_at is not None
    assert isinstance(instance.created_at, datetime)
