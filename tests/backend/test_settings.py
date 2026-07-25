"""Settings endpoint tests."""

from __future__ import annotations

from fastapi.testclient import TestClient


class TestSettingsEndpoint:
    def test_settings_returns_200(self, client: TestClient) -> None:
        response = client.get("/api/v1/settings")
        assert response.status_code == 200

    def test_settings_contains_top_level_fields(self, client: TestClient) -> None:
        response = client.get("/api/v1/settings")
        data = response.json()
        assert "app_name" in data
        assert "version" in data
        assert "environment" in data
        assert "debug" in data

    def test_settings_contains_nested_domains(self, client: TestClient) -> None:
        response = client.get("/api/v1/settings")
        data = response.json()
        assert "database" in data
        assert "logging" in data
        assert "server" in data
        assert "plugins" in data
        assert "paths" in data

    def test_settings_database_fields(self, client: TestClient) -> None:
        response = client.get("/api/v1/settings")
        db = response.json()["database"]
        assert "url" in db
        assert "echo" in db
        assert "pool_size" in db
        assert "max_overflow" in db

    def test_settings_server_fields(self, client: TestClient) -> None:
        response = client.get("/api/v1/settings")
        server = response.json()["server"]
        assert "host" in server
        assert "port" in server
        assert "allowed_origins" in server

    def test_settings_environment_value(self, client: TestClient) -> None:
        response = client.get("/api/v1/settings")
        assert response.json()["environment"] == "development"

    def test_settings_debug_enabled(self, client: TestClient) -> None:
        response = client.get("/api/v1/settings")
        assert response.json()["debug"] is True
