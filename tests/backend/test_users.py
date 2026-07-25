"""Tests for GET /users/{user_id} and PUT /users/{user_id}."""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient


# ═══════════════════════════════════════════════════════════════════════
#  GET /users/{user_id}
# ═══════════════════════════════════════════════════════════════════════


class TestGetUser:
    def test_get_nonexistent_returns_404(self, client: TestClient) -> None:
        resp = client.get(f"/api/v1/users/{uuid.uuid4()}")
        assert resp.status_code == 404

    def test_get_after_put_returns_user(self, client: TestClient) -> None:
        uid = uuid.uuid4()
        email = f"get_test_{uid}@example.com"
        client.put(f"/api/v1/users/{uid}", json={"email": email})
        resp = client.get(f"/api/v1/users/{uid}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == str(uid)
        assert data["email"] == email

    def test_get_response_contains_expected_fields(self, client: TestClient) -> None:
        uid = uuid.uuid4()
        client.put(f"/api/v1/users/{uid}", json={"email": f"fields_{uid}@example.com"})
        data = client.get(f"/api/v1/users/{uid}").json()
        for field in ("id", "email", "is_active", "is_verified", "created_at", "updated_at"):
            assert field in data, f"missing field: {field}"


# ═══════════════════════════════════════════════════════════════════════
#  PUT /users/{user_id} — upsert
# ═══════════════════════════════════════════════════════════════════════


class TestUpsertUser:
    def test_creates_new_user_row(self, client: TestClient) -> None:
        uid = uuid.uuid4()
        resp = client.put(f"/api/v1/users/{uid}", json={"email": f"create_{uid}@example.com"})
        assert resp.status_code == 200
        assert resp.json()["email"] == f"create_{uid}@example.com"

    def test_upsert_is_idempotent(self, client: TestClient) -> None:
        uid = uuid.uuid4()
        email = f"idempotent_{uid}@example.com"
        client.put(f"/api/v1/users/{uid}", json={"email": email})
        resp = client.put(f"/api/v1/users/{uid}", json={"email": email})
        assert resp.status_code == 200
        assert resp.json()["email"] == email

    def test_second_put_updates_email(self, client: TestClient) -> None:
        uid = uuid.uuid4()
        client.put(f"/api/v1/users/{uid}", json={"email": f"old_{uid}@example.com"})
        new_email = f"new_{uid}@example.com"
        resp = client.put(f"/api/v1/users/{uid}", json={"email": new_email})
        assert resp.status_code == 200
        assert resp.json()["email"] == new_email

    def test_put_without_email_creates_placeholder(self, client: TestClient) -> None:
        uid = uuid.uuid4()
        resp = client.put(f"/api/v1/users/{uid}", json={})
        assert resp.status_code == 200
        # Placeholder email must satisfy the DB NOT NULL constraint.
        assert resp.json()["email"] != ""

    def test_put_sets_is_active(self, client: TestClient) -> None:
        uid = uuid.uuid4()
        resp = client.put(
            f"/api/v1/users/{uid}",
            json={"email": f"active_{uid}@example.com", "is_active": False},
        )
        assert resp.status_code == 200
        assert resp.json()["is_active"] is False

    def test_put_invalid_email_returns_422(self, client: TestClient) -> None:
        uid = uuid.uuid4()
        resp = client.put(f"/api/v1/users/{uid}", json={"email": "not-an-email"})
        assert resp.status_code == 422

    def test_new_user_is_active_by_default(self, client: TestClient) -> None:
        uid = uuid.uuid4()
        resp = client.put(f"/api/v1/users/{uid}", json={"email": f"default_{uid}@example.com"})
        assert resp.json()["is_active"] is True


# ═══════════════════════════════════════════════════════════════════════
#  Profile creation auto-creates user (integration path)
# ═══════════════════════════════════════════════════════════════════════


class TestProfileCreationAutoCreatesUser:
    """POST /profiles should succeed even when no User row exists yet."""

    def test_create_profile_without_prior_user_row(self, client: TestClient) -> None:
        uid = uuid.uuid4()
        # No PUT /users first — profile endpoint must call get_or_create internally.
        resp = client.post("/api/v1/profiles", json={
            "user_id": str(uid),
            "display_name": "Auto-created user",
        })
        assert resp.status_code == 201
        assert resp.json()["display_name"] == "Auto-created user"

    def test_user_row_exists_after_profile_creation(self, client: TestClient) -> None:
        uid = uuid.uuid4()
        client.post("/api/v1/profiles", json={"user_id": str(uid), "display_name": "Auto"})
        resp = client.get(f"/api/v1/users/{uid}")
        assert resp.status_code == 200
        assert resp.json()["id"] == str(uid)


# ═══════════════════════════════════════════════════════════════════════
#  Digest skip-gracefully path
# ═══════════════════════════════════════════════════════════════════════


class TestDigestSkipGracefully:
    """Verify the digest callback skips silently when email is missing."""

    def test_digest_callback_skips_when_no_user_row(self) -> None:
        """_digest_callback returns early (no exception) when user row absent."""
        import uuid
        from unittest.mock import MagicMock, patch

        from core.config import AppConfig, BackgroundSchedulerSettings, NotificationSettings
        from services.background.tasks import _digest_callback

        uid = uuid.uuid4()
        config = MagicMock(spec=AppConfig)
        config.notifications = MagicMock(spec=NotificationSettings)
        config.notifications.email_enabled = True

        with patch("services.background.tasks.SessionLocal") as mock_sl, \
             patch("services.background.tasks.UserRepository") as mock_ur_cls:
            mock_db = MagicMock()
            mock_sl.return_value = mock_db

            mock_ur = MagicMock()
            mock_ur_cls.return_value = mock_ur
            # Simulate missing user row.
            mock_ur.get.return_value = None

            result = _digest_callback(uid, config)

        assert result == {"notifications_count": 0, "email_sent": False, "digest_id": None}

    def test_digest_callback_skips_when_placeholder_email(self) -> None:
        """_digest_callback returns early when user has a placeholder email."""
        import uuid
        from unittest.mock import MagicMock, patch

        from core.config import AppConfig, NotificationSettings
        from services.background.tasks import _digest_callback

        uid = uuid.uuid4()
        config = MagicMock(spec=AppConfig)
        config.notifications = MagicMock(spec=NotificationSettings)
        config.notifications.email_enabled = True

        fake_user = MagicMock()
        fake_user.email = f"placeholder-{uid}@no-email.invalid"

        with patch("services.background.tasks.SessionLocal") as mock_sl, \
             patch("services.background.tasks.UserRepository") as mock_ur_cls:
            mock_db = MagicMock()
            mock_sl.return_value = mock_db

            mock_ur = MagicMock()
            mock_ur_cls.return_value = mock_ur
            mock_ur.get.return_value = fake_user

            result = _digest_callback(uid, config)

        assert result == {"notifications_count": 0, "email_sent": False, "digest_id": None}
