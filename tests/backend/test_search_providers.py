"""Search provider listing endpoint tests."""

from __future__ import annotations

from fastapi.testclient import TestClient


class TestSearchProviders:
    def test_list_providers_includes_dummy(self, client: TestClient) -> None:
        resp = client.get("/api/v1/search-providers")
        assert resp.status_code == 200
        data = resp.json()
        names = [p["name"] for p in data]
        assert "dummy" in names

    def test_list_providers_response_structure(self, client: TestClient) -> None:
        resp = client.get("/api/v1/search-providers")
        assert resp.status_code == 200
        for provider in resp.json():
            assert "name" in provider

    def test_list_providers_sorted(self, client: TestClient) -> None:
        resp = client.get("/api/v1/search-providers")
        data = resp.json()
        names = [p["name"] for p in data]
        assert names == sorted(names)
