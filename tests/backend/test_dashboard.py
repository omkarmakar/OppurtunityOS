"""Dashboard endpoint tests."""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient


class TestDashboardEndpoint:
    def test_dashboard_requires_user_id(self, client: TestClient) -> None:
        resp = client.get("/api/v1/dashboard")
        assert resp.status_code == 422

    def test_dashboard_returns_empty_data(self, client: TestClient) -> None:
        uid = uuid.uuid4()
        resp = client.get(f"/api/v1/dashboard?user_id={uid}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["stats"]["total_opportunities"] == 0
        assert data["stats"]["total_searches"] == 0
        assert data["top_opportunities"] == []
        assert data["recent_searches"] == []
        assert data["upcoming_deadlines"] == []
        assert data["bookmarks"] == []
        assert len(data["score_distribution"]) == 5
        for d in data["score_distribution"]:
            assert d["count"] == 0
        assert data["status_breakdown"] == []
        assert len(data["daily_trend"]) == 14
        for d in data["daily_trend"]:
            assert d["count"] == 0

    def test_dashboard_response_structure(self, client: TestClient) -> None:
        uid = uuid.uuid4()
        resp = client.get(f"/api/v1/dashboard?user_id={uid}")
        data = resp.json()
        for section in (
            "stats", "top_opportunities", "recent_searches",
            "upcoming_deadlines", "bookmarks",
            "score_distribution", "status_breakdown", "daily_trend",
        ):
            assert section in data, f"Missing section: {section}"

    def test_dashboard_stats_structure(self, client: TestClient) -> None:
        uid = uuid.uuid4()
        resp = client.get(f"/api/v1/dashboard?user_id={uid}")
        stats = resp.json()["stats"]
        for field in (
            "total_opportunities", "total_searches", "total_bookmarks",
            "unread_notifications", "today_searches", "avg_relevance_score",
        ):
            assert field in stats, f"Missing stat: {field}"

    def test_dashboard_with_data(self, client: TestClient) -> None:
        uid = uuid.uuid4()
        client.post("/api/v1/profiles", json={
            "user_id": str(uid),
            "display_name": "Dash User",
            "skills": ["Python"],
        })
        resp = client.get(f"/api/v1/dashboard?user_id={uid}")
        assert resp.status_code == 200
        stats = resp.json()["stats"]
        assert stats["total_opportunities"] >= 0
        assert "total_bookmarks" in stats

    def test_dashboard_score_distribution_empty(self, client: TestClient) -> None:
        uid = uuid.uuid4()
        resp = client.get(f"/api/v1/dashboard?user_id={uid}")
        dist = resp.json()["score_distribution"]
        assert isinstance(dist, list)

    def test_dashboard_daily_trend_length(self, client: TestClient) -> None:
        uid = uuid.uuid4()
        resp = client.get(f"/api/v1/dashboard?user_id={uid}")
        trend = resp.json()["daily_trend"]
        assert len(trend) == 14
