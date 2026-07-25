"""Profile CRUD endpoint tests."""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient


class TestProfileCRUD:
    def test_create_profile(self, client: TestClient) -> None:
        uid = uuid.uuid4()
        resp = client.post("/api/v1/profiles", json={
            "user_id": str(uid),
            "display_name": "Test User",
            "bio": "A profile",
            "skills": ["Python"],
            "preferred_locations": ["Remote"],
            "target_companies": ["Google"],
            "keywords": ["backend"],
            "linkedin_url": "https://linkedin.com/in/test",
            "education": [{"institution": "MIT", "degree": "BS", "field": "CS", "start_date": "2018", "end_date": "2022"}],
            "experience": [{"company": "Acme", "role": "Dev", "description": "Built things", "start_date": "2022", "end_date": "present"}],
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["display_name"] == "Test User"
        assert data["skills"] == ["Python"]

    def test_create_duplicate_returns_409(self, client: TestClient) -> None:
        uid = uuid.uuid4()
        client.post("/api/v1/profiles", json={"user_id": str(uid), "display_name": "First"})
        resp = client.post("/api/v1/profiles", json={"user_id": str(uid), "display_name": "Second"})
        assert resp.status_code == 409

    def test_get_profile(self, client: TestClient) -> None:
        uid = uuid.uuid4()
        client.post("/api/v1/profiles", json={"user_id": str(uid), "display_name": "Getter"})
        resp = client.get(f"/api/v1/profiles/{uid}")
        assert resp.status_code == 200
        assert resp.json()["display_name"] == "Getter"

    def test_get_nonexistent_returns_404(self, client: TestClient) -> None:
        resp = client.get(f"/api/v1/profiles/{uuid.uuid4()}")
        assert resp.status_code == 404

    def test_update_profile(self, client: TestClient) -> None:
        uid = uuid.uuid4()
        client.post("/api/v1/profiles", json={"user_id": str(uid), "display_name": "Old"})
        resp = client.put(f"/api/v1/profiles/{uid}", json={"display_name": "Updated", "skills": ["Python", "Docker"]})
        assert resp.status_code == 200
        assert resp.json()["display_name"] == "Updated"
        assert resp.json()["skills"] == ["Python", "Docker"]

    def test_update_nonexistent_returns_404(self, client: TestClient) -> None:
        resp = client.put(f"/api/v1/profiles/{uuid.uuid4()}", json={"display_name": "Nope"})
        assert resp.status_code == 404

    def test_delete_profile(self, client: TestClient) -> None:
        uid = uuid.uuid4()
        client.post("/api/v1/profiles", json={"user_id": str(uid), "display_name": "Delete Me"})
        resp = client.delete(f"/api/v1/profiles/{uid}")
        assert resp.status_code == 204
        assert client.get(f"/api/v1/profiles/{uid}").status_code == 404

    def test_delete_nonexistent_returns_404(self, client: TestClient) -> None:
        resp = client.delete(f"/api/v1/profiles/{uuid.uuid4()}")
        assert resp.status_code == 404

    def test_profile_response_contains_all_fields(self, client: TestClient) -> None:
        uid = uuid.uuid4()
        resp = client.post("/api/v1/profiles", json={
            "user_id": str(uid),
            "display_name": "Full",
            "bio": "Bio text",
            "salary_expectations": "100k-150k",
            "resume_path": "/path/to/resume.pdf",
            "github_url": "https://github.com/user",
            "portfolio": "https://portfolio.dev",
            "skills": ["A", "B"],
            "preferred_locations": ["Remote"],
            "target_companies": ["C"],
            "keywords": ["D"],
            "education": [{"institution": "X", "degree": "Y", "field": "Z", "start_date": "2020", "end_date": "2024"}],
            "experience": [{"company": "W", "role": "V", "description": "U", "start_date": "2024", "end_date": "present"}],
        })
        data = resp.json()
        assert data["display_name"] == "Full"
        assert data["bio"] == "Bio text"
        assert data["salary_expectations"] == "100k-150k"
        assert data["resume_path"] == "/path/to/resume.pdf"
        assert data["github_url"] == "https://github.com/user"
        assert data["portfolio"] == "https://portfolio.dev"
        assert data["education"][0]["institution"] == "X"
        assert data["experience"][0]["company"] == "W"
