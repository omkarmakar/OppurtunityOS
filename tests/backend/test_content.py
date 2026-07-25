"""Content extraction endpoint tests."""

from __future__ import annotations

from fastapi.testclient import TestClient


class TestContentEndpoint:
    def test_extract_valid_url(self, client: TestClient) -> None:
        resp = client.post("/api/v1/content/extract", json={"url": "https://example.com"})
        assert resp.status_code == 200
        data = resp.json()
        assert "title" in data
        assert "content" in data
        assert "source_url" in data
        assert data["source_url"] == "https://example.com"

    def test_extract_missing_url_returns_422(self, client: TestClient) -> None:
        resp = client.post("/api/v1/content/extract", json={})
        assert resp.status_code == 422

    def test_extract_invalid_url_returns_422(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/content/extract",
            json={"url": "https://nonexistent-domain-xyz789.com/page"},
        )
        assert resp.status_code == 422

    def test_extract_response_structure(self, client: TestClient) -> None:
        resp = client.post("/api/v1/content/extract", json={"url": "https://example.com"})
        data = resp.json()
        for field in ("title", "content", "date", "author", "metadata", "source_url"):
            assert field in data, f"Missing field: {field}"
