"""Scoring endpoint tests."""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient


class TestScoringEndpoints:
    def _create_profile(self, client: TestClient) -> str:
        uid = uuid.uuid4()
        resp = client.post("/api/v1/profiles", json={
            "user_id": str(uid),
            "display_name": "Scorer User",
            "skills": ["Python", "FastAPI", "SQL", "Docker"],
            "preferred_locations": ["Remote"],
            "target_companies": ["Google"],
        })
        assert resp.status_code == 201
        return str(uid)

    def test_score_opportunity_requires_user_id(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/opportunities/score",
            json={"title": "Engineer"},
        )
        assert resp.status_code == 422

    def test_score_opportunity_404_without_profile(
        self, client: TestClient
    ) -> None:
        uid = uuid.uuid4()
        resp = client.post(
            f"/api/v1/opportunities/score?user_id={uid}",
            json={"title": "Engineer"},
        )
        assert resp.status_code == 404

    def test_score_opportunity_with_dummy_provider(
        self, client: TestClient
    ) -> None:
        user_id = self._create_profile(client)
        resp = client.post(
            f"/api/v1/opportunities/score?user_id={user_id}",
            json={
                "title": "Python Developer",
                "description": "Build APIs with FastAPI",
                "provider": "dummyai",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "relevance_score" in data
        assert "summary" in data
        assert "pros" in data
        assert "cons" in data
        assert "required_skills" in data
        assert "missing_skills" in data
        assert "application_deadline" in data
        assert "ranking_explanation" in data

    def test_score_opportunity_response_structure(
        self, client: TestClient
    ) -> None:
        user_id = self._create_profile(client)
        resp = client.post(
            f"/api/v1/opportunities/score?user_id={user_id}",
            json={
                "title": "Backend Engineer",
                "provider": "dummyai",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        for field in (
            "opportunity_id",
            "title",
            "url",
            "relevance_score",
            "summary",
            "pros",
            "cons",
            "required_skills",
            "missing_skills",
            "application_deadline",
            "ranking_explanation",
        ):
            assert field in data, f"Missing field: {field}"

    def test_score_and_save_with_dummy_provider(
        self, client: TestClient
    ) -> None:
        user_id = self._create_profile(client)
        resp = client.post(
            f"/api/v1/opportunities/score-and-save?user_id={user_id}",
            json={
                "opportunity_ids": [],
                "provider": "dummyai",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "results" in data
        assert data["results"] == []
