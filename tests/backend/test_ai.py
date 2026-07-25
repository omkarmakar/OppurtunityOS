"""AI service endpoint tests."""

from __future__ import annotations

from fastapi.testclient import TestClient


class TestAIEndpoints:
    def test_generate_with_dummy(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/ai/generate",
            json={
                "messages": [{"role": "user", "content": "hello world"}],
                "provider": "dummyai",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "content" in data
        assert "hello world" in data["content"]
        assert data["provider"] == "DummyAI"
        assert data["cached"] is False

    def test_generate_missing_messages_returns_422(self, client: TestClient) -> None:
        resp = client.post("/api/v1/ai/generate", json={})
        assert resp.status_code == 422

    def test_generate_invalid_provider_returns_400(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/ai/generate",
            json={
                "messages": [{"role": "user", "content": "hi"}],
                "provider": "nonexistent",
            },
        )
        assert resp.status_code == 400

    def test_list_providers(self, client: TestClient) -> None:
        resp = client.get("/api/v1/ai/providers")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        names = [p["name"] for p in data]
        assert "dummyai" in names

    def test_list_templates(self, client: TestClient) -> None:
        resp = client.get("/api/v1/ai/templates")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        names = [t["name"] for t in data]
        assert "summarize" in names
        assert "analyze" in names
        assert "custom" in names

    def test_generate_with_template(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/ai/generate",
            json={
                "messages": [{"role": "user", "content": "irrelevant"}],
                "provider": "dummyai",
                "prompt_template": "summarize",
                "template_vars": {"text": "Some long text here"},
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "Some long text here" in data["content"]

    def test_generate_with_unknown_template_returns_400(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/ai/generate",
            json={
                "messages": [{"role": "user", "content": "hi"}],
                "provider": "dummyai",
                "prompt_template": "nonexistent",
            },
        )
        assert resp.status_code == 400

    def test_generate_caching(self, client: TestClient) -> None:
        payload = {
            "messages": [{"role": "user", "content": "cache test"}],
            "provider": "dummyai",
            "use_cache": True,
        }
        resp1 = client.post("/api/v1/ai/generate", json=payload)
        assert resp1.status_code == 200
        data1 = resp1.json()
        assert data1["cached"] is False

        resp2 = client.post("/api/v1/ai/generate", json=payload)
        assert resp2.status_code == 200
        data2 = resp2.json()
        assert data2["cached"] is True
        assert data2["content"] == data1["content"]

    def test_generate_caching_skipped_when_disabled(self, client: TestClient) -> None:
        payload = {
            "messages": [{"role": "user", "content": "no cache"}],
            "provider": "dummyai",
            "use_cache": False,
        }
        resp1 = client.post("/api/v1/ai/generate", json=payload)
        assert resp1.status_code == 200

        resp2 = client.post("/api/v1/ai/generate", json=payload)
        assert resp2.status_code == 200
        data2 = resp2.json()
        assert data2["cached"] is False

    def test_count_tokens(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/ai/count-tokens",
            json=[
                {"role": "user", "content": "hello world"},
                {"role": "assistant", "content": "hi there"},
            ],
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "total_tokens" in data
        assert data["messages"] == 2
        assert data["total_tokens"] > 0

    def test_response_structure(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/ai/generate",
            json={
                "messages": [{"role": "user", "content": "test"}],
                "provider": "dummyai",
            },
        )
        data = resp.json()
        for field in ("content", "model", "provider", "usage", "cached", "finish_reason"):
            assert field in data, f"Missing field: {field}"
