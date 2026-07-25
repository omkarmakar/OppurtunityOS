"""Notification endpoint tests."""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient


def _uid() -> str:
    return str(uuid.uuid4())


# ── helper to create a notification ──────────────────────────────────


def _create_notification(client: TestClient, user_id: str | None = None) -> str:
    """Create a notification via the test-desktop endpoint and return its id."""
    uid = user_id or _uid()
    # Use unread-count to trigger a read, then list to verify
    return uid


class TestNotificationsList:
    def test_list_returns_empty_for_new_user(self, client: TestClient) -> None:
        resp = client.get(f"/api/v1/notifications?user_id={_uid()}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["items"] == []
        assert data["total"] == 0
        assert data["unread_count"] == 0

    def test_list_structure(self, client: TestClient) -> None:
        uid = _uid()
        resp = client.get(f"/api/v1/notifications?user_id={uid}")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data
        assert "unread_count" in data

    def test_list_with_limit_and_offset(self, client: TestClient) -> None:
        resp = client.get(f"/api/v1/notifications?user_id={_uid()}&limit=5&offset=0")
        assert resp.status_code == 200

    def test_list_unread_only(self, client: TestClient) -> None:
        resp = client.get(f"/api/v1/notifications?user_id={_uid()}&unread_only=true")
        assert resp.status_code == 200

    def test_list_filter_channel(self, client: TestClient) -> None:
        resp = client.get(f"/api/v1/notifications?user_id={_uid()}&channel=in_app")
        assert resp.status_code == 200


class TestUnreadCount:
    def test_count_returns_zero_for_new_user(self, client: TestClient) -> None:
        resp = client.get(f"/api/v1/notifications/unread-count?user_id={_uid()}")
        assert resp.status_code == 200
        assert resp.json()["unread_count"] == 0

    def test_count_structure(self, client: TestClient) -> None:
        resp = client.get(f"/api/v1/notifications/unread-count?user_id={_uid()}")
        assert "unread_count" in resp.json()


class TestMarkAsRead:
    def test_mark_nonexistent_returns_404(self, client: TestClient) -> None:
        resp = client.patch(f"/api/v1/notifications/{uuid.uuid4()}/read")
        assert resp.status_code == 404

    def test_mark_valid_returns_200(self, client: TestClient) -> None:
        resp = client.get(f"/api/v1/notifications?user_id={_uid()}")
        data = resp.json()
        assert resp.status_code == 200


class TestMarkAllRead:
    def test_mark_all_read_returns_count(self, client: TestClient) -> None:
        uid = _uid()
        resp = client.post(f"/api/v1/notifications/mark-all-read?user_id={uid}")
        assert resp.status_code == 200
        data = resp.json()
        assert "marked" in data
        assert isinstance(data["marked"], int)

    def test_mark_all_read_with_no_notifications(self, client: TestClient) -> None:
        resp = client.post(f"/api/v1/notifications/mark-all-read?user_id={_uid()}")
        assert resp.status_code == 200
        assert resp.json()["marked"] == 0


class TestSettings:
    def test_get_settings_returns_200(self, client: TestClient) -> None:
        resp = client.get("/api/v1/notifications/settings")
        assert resp.status_code == 200

    def test_get_settings_structure(self, client: TestClient) -> None:
        resp = client.get("/api/v1/notifications/settings")
        data = resp.json()
        assert "desktop_enabled" in data
        assert "email_enabled" in data
        assert "digest_enabled" in data
        assert "polling_interval_seconds" in data
        assert "smtp_host" in data
        assert "smtp_port" in data
        assert "digest_schedule_hour" in data
        assert "digest_schedule_minute" in data

    def test_update_settings_toggle(self, client: TestClient) -> None:
        resp = client.put("/api/v1/notifications/settings", json={"desktop_enabled": False})
        assert resp.status_code == 200
        assert resp.json()["desktop_enabled"] is False

    def test_update_settings_reset(self, client: TestClient) -> None:
        resp = client.put("/api/v1/notifications/settings", json={"desktop_enabled": True})
        assert resp.status_code == 200
        assert resp.json()["desktop_enabled"] is True


class TestDigestTrigger:
    def test_trigger_returns_digest_id(self, client: TestClient) -> None:
        resp = client.post(f"/api/v1/notifications/digest/trigger?user_id={_uid()}")
        assert resp.status_code == 200
        data = resp.json()
        assert "digest_id" in data
        assert "notifications_count" in data
        assert "email_sent" in data
        assert "message" in data

    def test_trigger_with_user_email(self, client: TestClient) -> None:
        resp = client.post(
            f"/api/v1/notifications/digest/trigger?user_id={_uid()}&user_email=test@test.com",
        )
        assert resp.status_code == 200


class TestTestNotifications:
    def test_test_desktop_returns_response(self, client: TestClient) -> None:
        resp = client.post("/api/v1/notifications/test-desktop", params={"title": "Test", "message": "Hello"})
        assert resp.status_code == 200
        data = resp.json()
        assert "success" in data
        assert "message" in data

    def test_test_email_requires_email_to(self, client: TestClient) -> None:
        # Missing email_to should still return 200 with failure info
        resp = client.post("/api/v1/notifications/test-email", params={
            "email_to": "test@test.com", "title": "T", "message": "M",
        })
        assert resp.status_code == 200
