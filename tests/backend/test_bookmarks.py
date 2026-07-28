"""Bookmark endpoint tests."""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient


class TestBookmarks:
    def _create_profile_with_opportunity(
        self, client: TestClient,
    ) -> tuple[uuid.UUID, uuid.UUID]:
        uid = uuid.uuid4()
        profile_resp = client.post(
            "/api/v1/profiles", json={"user_id": str(uid), "display_name": "Test"},
        )
        profile_id = profile_resp.json()["id"]
        resp = client.post(
            f"/api/v1/pipeline/run?profile_id={profile_id}&search_provider=dummy&max_queries=1&max_results=1",
        )
        # Get the opportunity ID from the list
        list_resp = client.get(f"/api/v1/opportunities?user_id={uid}")
        items = list_resp.json()["items"]
        assert len(items) >= 1
        return uid, items[0]["id"]

    def test_create_bookmark(self, client: TestClient) -> None:
        uid, opp_id = self._create_profile_with_opportunity(client)
        resp = client.post("/api/v1/bookmarks", json={
            "user_id": str(uid),
            "opportunity_id": str(opp_id),
            "notes": "Interesting opportunity",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["user_id"] == str(uid)
        assert data["opportunity_id"] == str(opp_id)
        assert data["notes"] == "Interesting opportunity"
        assert "id" in data

    def test_create_bookmark_duplicate_409(self, client: TestClient) -> None:
        uid, opp_id = self._create_profile_with_opportunity(client)
        client.post("/api/v1/bookmarks", json={
            "user_id": str(uid), "opportunity_id": str(opp_id),
        })
        resp = client.post("/api/v1/bookmarks", json={
            "user_id": str(uid), "opportunity_id": str(opp_id),
        })
        assert resp.status_code == 409

    def test_create_bookmark_missing_opportunity_404(self, client: TestClient) -> None:
        uid = uuid.uuid4()
        client.post("/api/v1/profiles", json={"user_id": str(uid), "display_name": "Test"})
        resp = client.post("/api/v1/bookmarks", json={
            "user_id": str(uid),
            "opportunity_id": str(uuid.uuid4()),
        })
        assert resp.status_code == 404

    def test_delete_bookmark(self, client: TestClient) -> None:
        uid, opp_id = self._create_profile_with_opportunity(client)
        create_resp = client.post("/api/v1/bookmarks", json={
            "user_id": str(uid), "opportunity_id": str(opp_id),
        })
        bm_id = create_resp.json()["id"]

        resp = client.delete(f"/api/v1/bookmarks/{bm_id}")
        assert resp.status_code == 204

    def test_delete_bookmark_404(self, client: TestClient) -> None:
        resp = client.delete(f"/api/v1/bookmarks/{uuid.uuid4()}")
        assert resp.status_code == 404

    def test_list_bookmarks(self, client: TestClient) -> None:
        uid, opp_id = self._create_profile_with_opportunity(client)
        client.post("/api/v1/bookmarks", json={
            "user_id": str(uid), "opportunity_id": str(opp_id),
            "notes": "My bookmark",
        })

        resp = client.get(f"/api/v1/bookmarks?user_id={uid}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        assert len(data["items"]) >= 1
        item = data["items"][0]
        assert item["opportunity_id"] == str(opp_id)
        assert "opportunity_title" in item
        assert "relevance_score" in item

    def test_update_bookmark_notes(self, client: TestClient) -> None:
        uid, opp_id = self._create_profile_with_opportunity(client)
        create_resp = client.post("/api/v1/bookmarks", json={
            "user_id": str(uid), "opportunity_id": str(opp_id), "notes": "original",
        })
        bm_id = create_resp.json()["id"]

        resp = client.patch(f"/api/v1/bookmarks/{bm_id}", json={"notes": "updated notes"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["notes"] == "updated notes"
        assert data["id"] == bm_id

    def test_update_bookmark_notes_404(self, client: TestClient) -> None:
        resp = client.patch(
            f"/api/v1/bookmarks/{uuid.uuid4()}",
            json={"notes": "test"},
        )
        assert resp.status_code == 404

    def test_update_bookmark_notes_empty(self, client: TestClient) -> None:
        uid, opp_id = self._create_profile_with_opportunity(client)
        create_resp = client.post("/api/v1/bookmarks", json={
            "user_id": str(uid), "opportunity_id": str(opp_id), "notes": "original",
        })
        bm_id = create_resp.json()["id"]

        resp = client.patch(f"/api/v1/bookmarks/{bm_id}", json={"notes": ""})
        assert resp.status_code == 200
        assert resp.json()["notes"] == ""

    def test_list_bookmarks_pagination(self, client: TestClient) -> None:
        uid, opp_id = self._create_profile_with_opportunity(client)
        client.post("/api/v1/bookmarks", json={
            "user_id": str(uid), "opportunity_id": str(opp_id),
        })

        resp = client.get(f"/api/v1/bookmarks?user_id={uid}&page=1&page_size=1")
        assert resp.status_code == 200
        data = resp.json()
        assert data["page"] == 1
        assert data["page_size"] == 1
        assert len(data["items"]) <= 1
