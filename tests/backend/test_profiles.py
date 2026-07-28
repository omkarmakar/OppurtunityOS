"""Profile CRUD endpoint tests."""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient


class TestProfileCRUD:
    def test_create_profile(self, client: TestClient) -> None:
        uid = uuid.uuid4()
        resp = client.post("/api/v1/profiles", json={
            "user_id": str(uid),
            "name": "R&D Track",
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
        assert data["name"] == "R&D Track"
        assert data["display_name"] == "Test User"
        assert data["skills"] == ["Python"]

    def test_create_second_profile_for_same_user_succeeds(self, client: TestClient) -> None:
        uid = uuid.uuid4()
        client.post("/api/v1/profiles", json={"user_id": str(uid), "name": "First"})
        resp = client.post("/api/v1/profiles", json={"user_id": str(uid), "name": "Second"})
        assert resp.status_code == 201
        assert resp.json()["name"] == "Second"

    def test_create_max_profiles_then_409(self, client: TestClient) -> None:
        uid = uuid.uuid4()
        for i in range(10):
            resp = client.post("/api/v1/profiles", json={
                "user_id": str(uid),
                "name": f"Profile {i+1}",
            })
            assert resp.status_code == 201

        # 11th should fail
        resp = client.post("/api/v1/profiles", json={
            "user_id": str(uid),
            "name": "Profile 11",
        })
        assert resp.status_code == 409
        assert "Maximum of 10 profiles" in resp.json()["detail"]

    def test_list_profiles(self, client: TestClient) -> None:
        uid = uuid.uuid4()
        client.post("/api/v1/profiles", json={"user_id": str(uid), "name": "Profile 1"})
        client.post("/api/v1/profiles", json={"user_id": str(uid), "name": "Profile 2"})

        resp = client.get(f"/api/v1/users/{uid}/profiles")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        names = [p["name"] for p in data]
        assert "Profile 1" in names
        assert "Profile 2" in names

    def test_get_profile_by_id(self, client: TestClient) -> None:
        uid = uuid.uuid4()
        create_resp = client.post("/api/v1/profiles", json={
            "user_id": str(uid),
            "name": "My Profile",
            "display_name": "Test",
        })
        profile_id = create_resp.json()["id"]

        resp = client.get(f"/api/v1/profiles/id/{profile_id}")
        assert resp.status_code == 200
        assert resp.json()["name"] == "My Profile"

    def test_get_nonexistent_profile_returns_404(self, client: TestClient) -> None:
        resp = client.get(f"/api/v1/profiles/id/{uuid.uuid4()}")
        assert resp.status_code == 404

    def test_update_profile_by_id(self, client: TestClient) -> None:
        uid = uuid.uuid4()
        create_resp = client.post("/api/v1/profiles", json={
            "user_id": str(uid),
            "name": "Old Name",
        })
        profile_id = create_resp.json()["id"]

        resp = client.put(f"/api/v1/profiles/id/{profile_id}", json={
            "name": "New Name",
            "display_name": "Updated",
        })
        assert resp.status_code == 200
        assert resp.json()["name"] == "New Name"
        assert resp.json()["display_name"] == "Updated"

    def test_update_nonexistent_returns_404(self, client: TestClient) -> None:
        resp = client.put(f"/api/v1/profiles/id/{uuid.uuid4()}", json={"name": "Nope"})
        assert resp.status_code == 404

    def test_delete_profile_by_id(self, client: TestClient) -> None:
        uid = uuid.uuid4()
        create_resp = client.post("/api/v1/profiles", json={
            "user_id": str(uid),
            "name": "Delete Me",
        })
        profile_id = create_resp.json()["id"]

        # Create a second profile so deletion is allowed
        client.post("/api/v1/profiles", json={"user_id": str(uid), "name": "Profile 2"})

        resp = client.delete(f"/api/v1/profiles/id/{profile_id}")
        assert resp.status_code == 204
        assert client.get(f"/api/v1/profiles/id/{profile_id}").status_code == 404

    def test_delete_last_profile_returns_409(self, client: TestClient) -> None:
        uid = uuid.uuid4()
        create_resp = client.post("/api/v1/profiles", json={
            "user_id": str(uid),
            "name": "Only Profile",
        })
        profile_id = create_resp.json()["id"]

        resp = client.delete(f"/api/v1/profiles/id/{profile_id}")
        assert resp.status_code == 409
        assert "Cannot delete the last remaining profile" in resp.json()["detail"]

    def test_delete_nonexistent_returns_404(self, client: TestClient) -> None:
        resp = client.delete(f"/api/v1/profiles/id/{uuid.uuid4()}")
        assert resp.status_code == 404

    def test_profile_response_contains_all_fields(self, client: TestClient) -> None:
        uid = uuid.uuid4()
        resp = client.post("/api/v1/profiles", json={
            "user_id": str(uid),
            "name": "Full Profile",
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
        assert data["name"] == "Full Profile"
        assert data["display_name"] == "Full"
        assert data["bio"] == "Bio text"
        assert data["salary_expectations"] == "100k-150k"
        assert data["resume_path"] == "/path/to/resume.pdf"
        assert data["github_url"] == "https://github.com/user"
        assert data["portfolio"] == "https://portfolio.dev"
        assert data["education"][0]["institution"] == "X"
        assert data["experience"][0]["company"] == "W"

    def test_profile_response_includes_new_resume_fields(self, client: TestClient) -> None:
        uid = uuid.uuid4()
        resp = client.post("/api/v1/profiles", json={
            "user_id": str(uid),
            "name": "Test Resume Fields",
            "remote_preference": "remote",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["raw_extracted_text"] is None
        assert data["resume_filename"] is None
        assert data["resume_uploaded_at"] is None
        assert data["remote_preference"] == "remote"