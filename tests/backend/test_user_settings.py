"""User settings endpoint tests."""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient


class TestUserSettings:
    def _create_user(self, client: TestClient) -> uuid.UUID:
        uid = uuid.uuid4()
        client.post("/api/v1/profiles", json={
            "user_id": str(uid),
            "display_name": "Settings Test",
        })
        return uid

    def test_get_settings_404_without_settings(self, client: TestClient) -> None:
        uid = uuid.uuid4()
        resp = client.get(f"/api/v1/user-settings?user_id={uid}")
        assert resp.status_code == 404

    def test_get_settings_after_create(self, client: TestClient) -> None:
        uid = self._create_user(client)
        resp = client.get(f"/api/v1/user-settings?user_id={uid}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["theme"] == "system"
        assert data["language"] == "en"
        assert data["notifications_enabled"] is True
        assert data["default_search_provider"] == "dummy"
        assert data["default_max_queries"] == 5
        assert data["default_max_results"] == 10

    def test_put_settings_updates_all_fields(self, client: TestClient) -> None:
        uid = self._create_user(client)
        resp = client.put(
            f"/api/v1/user-settings?user_id={uid}",
            json={
                "theme": "dark",
                "language": "fr",
                "notifications_enabled": False,
                "default_search_provider": "brave",
                "default_max_queries": 10,
                "default_max_results": 25,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["theme"] == "dark"
        assert data["language"] == "fr"
        assert data["notifications_enabled"] is False
        assert data["default_search_provider"] == "brave"
        assert data["default_max_queries"] == 10
        assert data["default_max_results"] == 25

    def test_put_settings_partial_update(self, client: TestClient) -> None:
        uid = self._create_user(client)
        resp = client.put(
            f"/api/v1/user-settings?user_id={uid}",
            json={"theme": "light"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["theme"] == "light"
        assert data["language"] == "en"

    def test_put_settings_404_without_profile(self, client: TestClient) -> None:
        uid = uuid.uuid4()
        resp = client.put(
            f"/api/v1/user-settings?user_id={uid}",
            json={"theme": "dark"},
        )
        assert resp.status_code == 404

    def test_settings_persist_across_calls(self, client: TestClient) -> None:
        uid = self._create_user(client)
        client.put(
            f"/api/v1/user-settings?user_id={uid}",
            json={"default_max_queries": 15},
        )
        resp = client.get(f"/api/v1/user-settings?user_id={uid}")
        assert resp.json()["default_max_queries"] == 15
