"""Opportunity endpoint tests."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi.testclient import TestClient


class TestOpportunities:
    def _create_profile(self, client: TestClient, uid: uuid.UUID | None = None) -> tuple[uuid.UUID, uuid.UUID]:
        uid = uid or uuid.uuid4()
        resp = client.post("/api/v1/profiles", json={"user_id": str(uid), "display_name": "Test"})
        return uid, resp.json()["id"]

    def _seed_opportunity(
        self, client: TestClient, profile_id: uuid.UUID,
        title: str = "Python Dev",
        status: str = "new",
        score: float | None = 85.0,
        url: str = "https://example.com/job",
    ) -> dict:
        # Use the pipeline to create an opportunity via the API
        resp = client.post(
            f"/api/v1/pipeline/run?profile_id={profile_id}&search_provider=dummy&max_queries=1&max_results=1",
        )
        assert resp.status_code == 200
        data = resp.json()
        # The dummy provider returns hardcoded results, so we can rely on at least one opportunity
        return data

    def test_list_opportunities_requires_user_id(self, client: TestClient) -> None:
        resp = client.get("/api/v1/opportunities")
        assert resp.status_code == 422

    def test_list_opportunities_empty(self, client: TestClient) -> None:
        uid = uuid.uuid4()
        resp = client.get(f"/api/v1/opportunities?user_id={uid}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["items"] == []

    def test_list_opportunities_pagination(self, client: TestClient) -> None:
        uid, pid = self._create_profile(client)
        for _ in range(3):
            self._seed_opportunity(client, pid)

        resp = client.get(f"/api/v1/opportunities?user_id={uid}&page=1&page_size=2")
        assert resp.status_code == 200
        data = resp.json()
        assert data["page"] == 1
        assert data["page_size"] == 2
        assert len(data["items"]) <= 2
        assert data["total"] >= 1

    def test_get_opportunity_by_id(self, client: TestClient) -> None:
        uid, pid = self._create_profile(client)
        self._seed_opportunity(client, pid)

        list_resp = client.get(f"/api/v1/opportunities?user_id={uid}")
        items = list_resp.json()["items"]
        assert len(items) >= 1
        opp_id = items[0]["id"]

        resp = client.get(f"/api/v1/opportunities/{opp_id}")
        assert resp.status_code == 200
        detail = resp.json()
        assert detail["id"] == opp_id
        assert "title" in detail
        assert "relevance_score" in detail

    def test_get_opportunity_404(self, client: TestClient) -> None:
        resp = client.get(f"/api/v1/opportunities/{uuid.uuid4()}")
        assert resp.status_code == 404

    def test_update_status(self, client: TestClient) -> None:
        uid, pid = self._create_profile(client)
        self._seed_opportunity(client, pid)

        list_resp = client.get(f"/api/v1/opportunities?user_id={uid}")
        opp_id = list_resp.json()["items"][0]["id"]

        resp = client.patch(
            f"/api/v1/opportunities/{opp_id}/status",
            json={"status": "applied"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "applied"

    def test_update_status_invalid_value(self, client: TestClient) -> None:
        uid, pid = self._create_profile(client)
        self._seed_opportunity(client, pid)

        list_resp = client.get(f"/api/v1/opportunities?user_id={uid}")
        opp_id = list_resp.json()["items"][0]["id"]

        resp = client.patch(
            f"/api/v1/opportunities/{opp_id}/status",
            json={"status": "invalid_status"},
        )
        assert resp.status_code == 422

    def test_update_status_404(self, client: TestClient) -> None:
        resp = client.patch(
            f"/api/v1/opportunities/{uuid.uuid4()}/status",
            json={"status": "applied"},
        )
        assert resp.status_code == 404

    def test_filter_by_status(self, client: TestClient) -> None:
        uid, pid = self._create_profile(client)
        self._seed_opportunity(client, pid)

        resp = client.get(f"/api/v1/opportunities?user_id={uid}&status=new")
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["status"] == "new"

    def test_filter_by_min_score(self, client: TestClient) -> None:
        uid, pid = self._create_profile(client)
        self._seed_opportunity(client, pid)

        resp = client.get(f"/api/v1/opportunities?user_id={uid}&min_score=50")
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            score = item.get("relevance_score")
            assert score is None or score >= 50
