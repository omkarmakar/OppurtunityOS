"""Version endpoint tests."""

from __future__ import annotations

from fastapi.testclient import TestClient


class TestVersionEndpoint:
    def test_version_returns_200(self, client: TestClient) -> None:
        response = client.get("/api/v1/version")
        assert response.status_code == 200

    def test_version_contains_required_fields(self, client: TestClient) -> None:
        response = client.get("/api/v1/version")
        data = response.json()
        assert "name" in data
        assert "version" in data
        assert "python" in data

    def test_version_name(self, client: TestClient) -> None:
        response = client.get("/api/v1/version")
        assert response.json()["name"] == "OpportunityOS"

    def test_version_string_format(self, client: TestClient) -> None:
        response = client.get("/api/v1/version")
        version = response.json()["version"]
        parts = version.split(".")
        assert len(parts) == 3
        assert all(p.isdigit() for p in parts)

    def test_python_version_format(self, client: TestClient) -> None:
        response = client.get("/api/v1/version")
        py = response.json()["python"]
        parts = py.split(".")
        assert len(parts) == 3
        assert all(p.isdigit() for p in parts)
