"""Pipeline trigger endpoint tests."""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient


class TestPipelineEndpoint:
    def test_run_pipeline_requires_user_id(self, client: TestClient) -> None:
        resp = client.post("/api/v1/pipeline/run")
        assert resp.status_code == 422

    def test_run_pipeline_404_without_profile(self, client: TestClient) -> None:
        uid = uuid.uuid4()
        resp = client.post(f"/api/v1/pipeline/run?user_id={uid}")
        assert resp.status_code == 404

    def test_run_pipeline_with_dummy(self, client: TestClient) -> None:
        uid = uuid.uuid4()
        client.post("/api/v1/profiles", json={
            "user_id": str(uid),
            "display_name": "Pipeline User",
            "skills": ["Python"],
        })

        resp = client.post(
            f"/api/v1/pipeline/run?user_id={uid}&search_provider=dummy&max_queries=2&max_results=3",
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert "queries_generated" in data
        assert "search_results_count" in data
        assert "opportunities_created" in data

    def test_run_pipeline_skip_ranking(self, client: TestClient) -> None:
        uid = uuid.uuid4()
        client.post("/api/v1/profiles", json={
            "user_id": str(uid),
            "display_name": "Skip Rank",
            "skills": ["Python"],
        })

        resp = client.post(
            f"/api/v1/pipeline/run?user_id={uid}"
            f"&search_provider=dummy&max_queries=1&max_results=2&skip_ranking=true",
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["opportunities_scored"] == 0

    def test_run_pipeline_response_structure(self, client: TestClient) -> None:
        uid = uuid.uuid4()
        client.post("/api/v1/profiles", json={
            "user_id": str(uid),
            "display_name": "Structure Test",
            "skills": ["Python"],
        })

        resp = client.post(
            f"/api/v1/pipeline/run?user_id={uid}&search_provider=dummy&max_queries=1&max_results=1",
        )
        assert resp.status_code == 200
        data = resp.json()
        for field in (
            "success", "queries_generated", "search_results_count",
            "pages_extracted", "opportunities_created", "opportunities_scored",
            "notifications_sent", "error",
        ):
            assert field in data, f"Missing field: {field}"
