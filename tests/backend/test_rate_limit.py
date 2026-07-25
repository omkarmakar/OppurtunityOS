"""Tests for the rate limit middleware."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.middleware.rate_limit import RateLimitMiddleware


@pytest.fixture
def app():
    _app = FastAPI()
    _app.add_middleware(RateLimitMiddleware, default_limit=5, window_seconds=60)
    @_app.get("/test")
    async def test_endpoint():
        return {"ok": True}
    return _app


@pytest.fixture
def client(app):
    return TestClient(app)


class TestRateLimit:
    def test_allows_normal_requests(self, client):
        for _ in range(5):
            resp = client.get("/test")
            assert resp.status_code == 200

    def test_blocks_excess_requests(self, client):
        for _ in range(5):
            client.get("/test")
        resp = client.get("/test")
        assert resp.status_code == 429
        assert "rate limit" in resp.text.lower()

    def test_exempts_health_endpoint(self, app):
        @app.get("/api/v1/health")
        async def health():
            return {"status": "ok"}
        client = TestClient(app)
        for _ in range(20):
            resp = client.get("/api/v1/health")
            assert resp.status_code == 200

    def test_route_specific_limits(self):
        _app = FastAPI()
        _app.add_middleware(
            RateLimitMiddleware,
            default_limit=10,
            window_seconds=60,
            route_limits={"/expensive": 2},
        )
        @_app.get("/expensive")
        async def expensive():
            return {"ok": True}
        client = TestClient(_app)
        for _ in range(2):
            assert client.get("/expensive").status_code == 200
        assert client.get("/expensive").status_code == 429
