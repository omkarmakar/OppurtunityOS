"""Notification service tests."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.orm import Session

from core.config import AppConfig
from database.models.notifications import Notification
from database.models.users import User
from database.repositories.notification_repository import NotificationRepository
from services.notifications import (
    DailyDigestService,
    DesktopNotificationProvider,
    EmailNotificationProvider,
    NotificationScheduler,
    NotificationService,
)


# ── helpers ──────────────────────────────────────────────────────────


def _user(db_session: Session) -> uuid.UUID:
    """Create a minimal User row and return its id."""
    uid = uuid.uuid4()
    db_session.add(User(id=uid, email=f"{uid}@test.com", password_hash="test-hash"))
    db_session.commit()
    return uid


# ── NotificationService ──────────────────────────────────────────────


class TestNotificationService:
    def test_create_notification(self, db_session: Session) -> None:
        svc = NotificationService(db_session)
        uid = _user(db_session)
        notif = svc.create_notification(
            user_id=uid,
            type_="test",
            title="Test Title",
            message="Test message",
            channel="in_app",
        )
        assert notif.id is not None
        assert notif.user_id == uid
        assert notif.title == "Test Title"
        assert notif.message == "Test message"
        assert notif.channel == "in_app"
        assert notif.is_read is False
        assert notif.type_ == "test"

    def test_create_notification_with_metadata(self, db_session: Session) -> None:
        svc = NotificationService(db_session)
        uid = _user(db_session)
        notif = svc.create_notification(
            user_id=uid,
            type_="scored",
            title="Opportunity Scored",
            metadata={"score": 85, "tags": ["python", "backend"]},
        )
        import json
        assert json.loads(notif.metadata_json) == {"score": 85, "tags": ["python", "backend"]}

    def test_send_notification_creates_record(self, db_session: Session) -> None:
        svc = NotificationService(db_session)
        uid = _user(db_session)
        notif = svc.send_notification(
            user_id=uid,
            type_="desktop_test",
            title="Desktop",
            message="Hello",
            channel="desktop",
        )
        assert notif.id is not None
        assert notif.channel == "desktop"

    def test_get_notifications_empty(self, db_session: Session) -> None:
        svc = NotificationService(db_session)
        items = svc.get_notifications(_user(db_session))
        assert items == []

    def test_get_notifications_with_data(self, db_session: Session) -> None:
        svc = NotificationService(db_session)
        uid = _user(db_session)
        svc.create_notification(uid, "info", "First")
        svc.create_notification(uid, "info", "Second")
        items = svc.get_notifications(uid)
        assert len(items) == 2

    def test_get_notifications_unread_only(self, db_session: Session) -> None:
        svc = NotificationService(db_session)
        uid = _user(db_session)
        n1 = svc.create_notification(uid, "info", "Read this")
        svc.create_notification(uid, "info", "Unread")
        svc.mark_as_read(n1.id)
        items = svc.get_notifications(uid, unread_only=True)
        assert len(items) == 1
        assert items[0].title == "Unread"

    def test_get_notifications_filter_channel(self, db_session: Session) -> None:
        svc = NotificationService(db_session)
        uid = _user(db_session)
        svc.create_notification(uid, "info", "In-app", channel="in_app")
        svc.create_notification(uid, "info", "Desktop", channel="desktop")
        items = svc.get_notifications(uid, channel="desktop")
        assert len(items) == 1
        assert items[0].title == "Desktop"

    def test_get_notifications_pagination(self, db_session: Session) -> None:
        svc = NotificationService(db_session)
        uid = _user(db_session)
        for i in range(10):
            svc.create_notification(uid, "info", f"Notif {i}")
        items = svc.get_notifications(uid, limit=3, offset=0)
        assert len(items) == 3
        items2 = svc.get_notifications(uid, limit=3, offset=3)
        assert len(items2) == 3
        assert items[0].id != items2[0].id

    def test_count_unread(self, db_session: Session) -> None:
        svc = NotificationService(db_session)
        uid = _user(db_session)
        assert svc.count_unread(uid) == 0
        svc.create_notification(uid, "info", "Unread 1")
        svc.create_notification(uid, "info", "Unread 2")
        assert svc.count_unread(uid) == 2

    def test_mark_as_read_returns_none_for_missing(self, db_session: Session) -> None:
        svc = NotificationService(db_session)
        result = svc.mark_as_read(uuid.uuid4())
        assert result is None

    def test_mark_as_read(self, db_session: Session) -> None:
        svc = NotificationService(db_session)
        uid = _user(db_session)
        notif = svc.create_notification(uid, "info", "Mark me")
        assert notif.is_read is False
        updated = svc.mark_as_read(notif.id)
        assert updated is not None
        assert updated.is_read is True
        assert updated.read_at is not None

    def test_mark_all_as_read(self, db_session: Session) -> None:
        svc = NotificationService(db_session)
        uid = _user(db_session)
        svc.create_notification(uid, "info", "A")
        svc.create_notification(uid, "info", "B")
        svc.create_notification(uid, "info", "C")
        count = svc.mark_all_as_read(uid)
        assert count == 3
        assert svc.count_unread(uid) == 0

    def test_get_total_count(self, db_session: Session) -> None:
        svc = NotificationService(db_session)
        uid = _user(db_session)
        assert svc.get_total_count(uid) == 0
        svc.create_notification(uid, "info", "X")
        svc.create_notification(uid, "info", "Y")
        assert svc.get_total_count(uid) == 2

    def test_service_init_with_config(self, db_session: Session) -> None:
        config = AppConfig()
        config.notifications.desktop_enabled = False
        config.notifications.email_enabled = False
        svc = NotificationService(db_session, config=config)
        assert svc._desktop_provider is None
        assert svc._email_provider is None


# ── DesktopNotificationProvider ──────────────────────────────────────


class TestDesktopNotificationProvider:
    def test_send_fallback_when_no_tray(self) -> None:
        with patch.object(DesktopNotificationProvider, "_init_tray", return_value=None):
            provider = DesktopNotificationProvider()
            provider._tray_icon = None
            result = provider.send("test", "Title", "Message")
            assert result is False

    def test_init_does_not_crash_without_app(self) -> None:
        provider = DesktopNotificationProvider()
        assert provider is not None


# ── EmailNotificationProvider ────────────────────────────────────────


class TestEmailNotificationProvider:
    def test_send_without_email_to_returns_false(self) -> None:
        provider = EmailNotificationProvider()
        result = provider.send("test", "Title", "Msg")
        assert result is False

    def test_send_with_email_attempts_smtp(self) -> None:
        with patch("smtplib.SMTP") as mock_smtp:
            provider = EmailNotificationProvider(
                host="smtp.test.com",
                port=587,
                username="user",
                password="pass",
                use_tls=True,
                from_address="test@test.com",
                from_name="Tester",
            )
            result = provider.send("test", "Hello", "Body", email_to="user@test.com")
            assert result is True
            mock_smtp.assert_called_once_with("smtp.test.com", 587, timeout=10)
            instance = mock_smtp.return_value.__enter__.return_value
            instance.starttls.assert_called_once()
            instance.login.assert_called_once_with("user", "pass")

    def test_send_without_tls(self) -> None:
        with patch("smtplib.SMTP") as mock_smtp:
            provider = EmailNotificationProvider(use_tls=False)
            provider.send("test", "Hi", "Body", email_to="a@b.com")
            instance = mock_smtp.return_value.__enter__.return_value
            instance.starttls.assert_not_called()

    def test_smtp_failure_returns_false(self) -> None:
        with patch("smtplib.SMTP", side_effect=ConnectionError("No connection")):
            provider = EmailNotificationProvider()
            result = provider.send("test", "Hi", "Body", email_to="a@b.com")
            assert result is False


# ── DailyDigestService ────────────────────────────────────────────────


class TestDailyDigestService:
    def test_run_empty_returns_zero(self, db_session: Session) -> None:
        svc = DailyDigestService(db_session)
        result = svc.run(_user(db_session))
        assert result["notifications_count"] == 0
        assert result["email_sent"] is False
        assert result["digest_id"] is None

    def test_run_creates_digest(self, db_session: Session) -> None:
        svc = NotificationService(db_session)
        uid = _user(db_session)
        svc.create_notification(uid, "info", "Unread A")
        svc.create_notification(uid, "warning", "Unread B")

        digest_svc = DailyDigestService(db_session)
        result = digest_svc.run(uid)
        assert result["notifications_count"] == 2
        assert result["digest_id"] is not None

        repo = NotificationRepository(db_session)
        digests = repo.list_unread_by_channel(uid, "in_app")
        digest_items = [n for n in digests if n.type_ == "digest"]
        assert len(digest_items) == 1
        assert digest_items[0].title == "Daily Digest"
        assert "Unread A" in (digest_items[0].message or "")

        original = repo.list_by_user_id(uid)
        for n in original:
            if n.type_ != "digest":
                assert n.digest_id is not None

    def test_run_with_email(self, db_session: Session) -> None:
        svc = NotificationService(db_session)
        uid = _user(db_session)
        svc.create_notification(uid, "info", "Digest item")

        email_mock = MagicMock()
        email_mock.send.return_value = True

        settings = AppConfig().notifications.digest
        digest_svc = DailyDigestService(db_session, email_provider=email_mock, settings=settings)
        result = digest_svc.run(uid, user_email="user@test.com")
        assert result["notifications_count"] == 1
        assert result["email_sent"] is True
        email_mock.send.assert_called_once()

    def test_build_summary_format(self) -> None:
        n1 = Notification(type_="info", title="Test A")
        n2 = Notification(type_="warning", title="Test B")
        summary = DailyDigestService._build_summary([n1, n2])
        assert "2 new notification" in summary["text"]
        assert "Test A" in summary["text"]
        assert "Test B" in summary["text"]
        assert summary["metadata"]["total"] == 2
        assert summary["metadata"]["type_counts"] == {"info": 1, "warning": 1}

    def test_email_sends_regardless_of_include_unread_only_setting(self, db_session: Session) -> None:
        """Test that include_unread_only doesn't gate email sending."""
        svc = NotificationService(db_session)
        uid = _user(db_session)
        svc.create_notification(uid, "info", "Digest item")

        email_mock = MagicMock()
        email_mock.send.return_value = True

        config = AppConfig()
        config.notifications.digest.include_unread_only = False  # This should NOT prevent email
        digest_svc = DailyDigestService(db_session, email_provider=email_mock, settings=config.notifications.digest)
        result = digest_svc.run(uid, user_email="user@test.com")
        
        # Email should still be sent despite include_unread_only=False
        assert result["email_sent"] is True
        email_mock.send.assert_called_once()

    def test_digest_body_includes_opportunity_score_and_url(self, db_session: Session) -> None:
        """Test that opportunity notifications in digest include score and URL from metadata."""
        import json

        svc = NotificationService(db_session)
        uid = _user(db_session)
        
        # Create an opportunity notification with metadata
        metadata = {
            "opportunity_id": "opp123",
            "score": 87.5,
            "url": "https://example.com/job",
        }
        svc.create_notification(
            uid, "opportunity",
            title="New opportunity: Research Intern",
            message="Score: 88/100 — https://example.com/job",
            channel="in_app",
            metadata=metadata,
        )
        
        # Build digest
        digest_svc = DailyDigestService(db_session)
        result = digest_svc.run(uid)
        
        assert result["notifications_count"] == 1
        
        # Check the digest body includes score and URL
        summary_text = result.get("digest_text", "")
        
        # Get the digest from the database to check the actual body
        repo = NotificationRepository(db_session)
        digests = repo.list_unread_by_channel(uid, "in_app")
        digest_notif = next((n for n in digests if n.type_ == "digest"), None)
        assert digest_notif is not None
        
        digest_body = digest_notif.message or ""
        # Should include score information
        assert "score" in digest_body.lower() or "87" in digest_body or "88" in digest_body
        # Should include URL
        assert "https://example.com/job" in digest_body or "example.com" in digest_body

    def test_digest_respects_include_unread_only_for_query(self, db_session: Session) -> None:
        """Test that include_unread_only still affects which notifications are queried for digest content."""
        svc = NotificationService(db_session)
        uid = _user(db_session)
        
        # Create multiple notifications
        n1 = svc.create_notification(uid, "info", "Unread notification")
        n2 = svc.create_notification(uid, "warning", "Read notification")
        svc.mark_as_read(n2.id)
        
        config = AppConfig()
        config.notifications.digest.include_unread_only = True  # Only include unread
        digest_svc = DailyDigestService(db_session, settings=config.notifications.digest)
        result = digest_svc.run(uid)
        
        # Only unread notification should be in digest
        assert result["notifications_count"] == 1
        
        repo = NotificationRepository(db_session)
        digests = repo.list_unread_by_channel(uid, "in_app")
        digest_notif = next((n for n in digests if n.type_ == "digest"), None)
        assert digest_notif is not None
        assert "Unread notification" in (digest_notif.message or "")


# ── NotificationScheduler ────────────────────────────────────────────


class TestNotificationScheduler:
    def test_start_stop(self) -> None:
        scheduler = NotificationScheduler(polling_interval=10)
        assert scheduler.running is False
        scheduler.start()
        assert scheduler.running is True
        scheduler.stop()
        assert scheduler.running is False

    def test_start_idempotent(self) -> None:
        scheduler = NotificationScheduler(polling_interval=10)
        scheduler.start()
        old_thread = scheduler._thread
        scheduler.start()
        assert scheduler._thread is old_thread
        scheduler.stop()

    def test_does_not_trigger_before_schedule(self) -> None:
        callback = MagicMock()
        scheduler = NotificationScheduler(
            digest_callback=callback,
            polling_interval=1,
            digest_hour=99,  # will never match
        )
        scheduler._check_digest()
        callback.assert_not_called()
        scheduler.stop()

    def test_triggers_at_scheduled_time(self) -> None:
        callback = MagicMock()
        now = datetime.now()
        scheduler = NotificationScheduler(
            digest_callback=callback,
            polling_interval=1,
            digest_hour=now.hour,
            digest_minute=now.minute,
        )
        scheduler._check_digest()
        callback.assert_called_once()
        assert scheduler._last_digest_date == now.date()
        scheduler.stop()

    def test_does_not_trigger_twice_same_day(self) -> None:
        callback = MagicMock()
        now = datetime.now()
        scheduler = NotificationScheduler(
            digest_callback=callback,
            polling_interval=1,
            digest_hour=now.hour,
            digest_minute=now.minute,
        )
        scheduler._check_digest()
        scheduler._check_digest()
        callback.assert_called_once()
        scheduler.stop()
