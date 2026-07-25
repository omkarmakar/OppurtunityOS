"""Health endpoint tests."""

from __future__ import annotations

from fastapi.testclient import TestClient


class TestHealthEndpoint:
    def test_health_check_returns_healthy(self, client: TestClient) -> None:
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

    def test_health_check_contains_database_field(self, client: TestClient) -> None:
        response = client.get("/api/v1/health")
        data = response.json()
        assert "database" in data

    def test_health_check_database_connected(self, client: TestClient) -> None:
        response = client.get("/api/v1/health")
        assert response.json()["database"] == "connected"
