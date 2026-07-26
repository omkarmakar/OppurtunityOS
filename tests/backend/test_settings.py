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

    def test_settings_has_configuration_status(self, client: TestClient) -> None:
        response = client.get("/api/v1/settings")
        data = response.json()
        assert "configuration_status" in data
        assert len(data["configuration_status"]) >= 1

    def test_configuration_status_structure(self, client: TestClient) -> None:
        response = client.get("/api/v1/settings")
        for item in response.json()["configuration_status"]:
            assert "name" in item
            assert "configured" in item
            assert isinstance(item["configured"], bool)
            assert "env_var" in item

    def test_groq_in_configuration_status(self, client: TestClient) -> None:
        response = client.get("/api/v1/settings")
        for item in response.json()["configuration_status"]:
            if item["name"] == "groq":
                return
        assert False, "groq not found in configuration_status"

    def test_dummyai_not_in_configuration_status(self, client: TestClient) -> None:
        response = client.get("/api/v1/settings")
        for item in response.json()["configuration_status"]:
            if item["name"] == "dummyai":
                assert False, "dummyai should not appear in configuration_status"

    def test_ollama_always_configured(self, client: TestClient) -> None:
        response = client.get("/api/v1/settings")
        for item in response.json()["configuration_status"]:
            if item["name"] == "ollama":
                assert item["configured"] is True
                return
        assert False, "ollama not found in configuration_status"

    def test_settings_redaction_no_config_keys_in_response(self, client: TestClient) -> None:
        response = client.get("/api/v1/settings")
        raw = response.text
        assert "sk-" not in raw
        assert "AIza" not in raw
