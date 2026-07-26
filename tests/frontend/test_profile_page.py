"""Tests for the Profile page (multi-profile switcher + form)."""

from __future__ import annotations

from unittest.mock import patch

import httpx
import pytest
from pytestqt.qtbot import QtBot

from frontend.pages.profile import (
    MAX_PROFILES,
    NewProfileCard,
    ProfileCard,
    ProfilePage,
)
from frontend.widgets.profile_form import ProfileForm, TagInput

SAMPLE_PROFILE = {
    "id": "p1",
    "user_id": "u1",
    "name": "AI/ML Track",
    "display_name": "Om",
    "bio": "AI researcher",
    "skills": ["Python", "TensorFlow"],
    "education": [{"institution": "MIT", "degree": "B.S.", "field": "CS", "start_date": "2018", "end_date": "2022"}],
    "experience": [],
    "projects": [],
    "preferred_locations": ["SF"],
    "target_companies": [],
    "keywords": [],
    "salary_expectations": "150k",
    "linkedin_url": "",
    "github_url": "",
    "portfolio": "",
    "avatar_url": None,
    "resume_path": None,
    "created_at": "2026-01-01T00:00:00",
    "updated_at": "2026-01-01T00:00:00",
}

SAMPLE_PROFILE_2 = {**SAMPLE_PROFILE, "id": "p2", "name": "R&D Track", "display_name": "Om R&D"}
SAMPLE_PROFILE_3 = {**SAMPLE_PROFILE, "id": "p3", "name": "Data Science"}


def _mock_get(json_data, status_code=200):
    """Return a patch-compatible mock for httpx.get."""
    m = patch.object(httpx, "get")
    mr = m.start()
    resp = mr.return_value
    resp.json.return_value = json_data
    resp.raise_for_status.return_value = None
    resp.status_code = status_code
    return m


class TestTagInput:
    def test_add_tag(self, qtbot: QtBot) -> None:
        w = TagInput()
        qtbot.add_widget(w)
        w._input.setText("Python")
        w._add_tag()
        assert w.get_tags() == ["Python"]

    def test_set_tags(self, qtbot: QtBot) -> None:
        w = TagInput()
        qtbot.add_widget(w)
        w.set_tags(["A", "B"])
        assert w.get_tags() == ["A", "B"]


class TestProfileForm:
    def test_widget_structure(self, qtbot: QtBot) -> None:
        form = ProfileForm()
        qtbot.add_widget(form)
        assert form._name is not None
        assert form._display_name is not None
        assert form._bio is not None
        assert form._skills is not None
        assert form._salary is not None
        assert form._linkedin is not None
        assert form._github is not None
        assert form._portfolio is not None
        assert form._save_btn is not None

    def test_populate_and_collect(self, qtbot: QtBot) -> None:
        form = ProfileForm()
        qtbot.add_widget(form)
        form.populate(SAMPLE_PROFILE)
        assert form._name.text() == "AI/ML Track"
        assert form._display_name.text() == "Om"
        data = form.collect()
        assert data["name"] == "AI/ML Track"
        assert data["display_name"] == "Om"
        assert "Python" in data["skills"]

    def test_clear_after_populate(self, qtbot: QtBot) -> None:
        form = ProfileForm()
        qtbot.add_widget(form)
        form.populate(SAMPLE_PROFILE)
        form.clear()
        assert form._name.text() == ""
        assert form._skills.get_tags() == []
        assert form.get_profile_id() is None

    def test_set_name_suggestion(self, qtbot: QtBot) -> None:
        form = ProfileForm()
        qtbot.add_widget(form)
        form.set_name_suggestion("Software Engineer Track")
        assert form._name.text() == "Software Engineer Track"


class TestNewProfileCard:
    def test_enabled_by_default(self, qtbot: QtBot) -> None:
        card = NewProfileCard()
        qtbot.add_widget(card)
        assert card.isEnabled() is True
        assert card.toolTip() == ""

    def test_disabled_at_limit(self, qtbot: QtBot) -> None:
        card = NewProfileCard()
        qtbot.add_widget(card)
        card.set_disabled(True)
        assert card.isEnabled() is False
        assert f"{MAX_PROFILES}" in card.toolTip()


class TestProfilePage:
    def test_title(self, qtbot: QtBot) -> None:
        page = ProfilePage()
        qtbot.add_widget(page)
        assert page._title == "Profile"

    def test_empty_state_shown_when_no_profiles(self, qtbot: QtBot) -> None:
        with patch.object(httpx, "get") as mock_get:
            resp = mock_get.return_value
            resp.json.return_value = []
            resp.raise_for_status.return_value = None
            resp.status_code = 200
            page = ProfilePage()
            qtbot.add_widget(page)
            assert page._empty_widget.isVisible()
            assert page._switcher_widget.isVisible() is False
            assert page._form_container.isVisible() is False

    def test_empty_state_visible(self, qtbot: QtBot) -> None:
        with patch.object(httpx, "get") as mock_get:
            resp = mock_get.return_value
            resp.json.return_value = []
            resp.raise_for_status.return_value = None
            resp.status_code = 200
            page = ProfilePage()
            qtbot.add_widget(page)
            assert page._empty_widget.isVisible()

    def test_switcher_shown_when_profiles_exist(self, qtbot: QtBot) -> None:
        with patch.object(httpx, "get") as mock_get:
            resp = mock_get.return_value
            resp.json.return_value = [SAMPLE_PROFILE]
            resp.raise_for_status.return_value = None
            resp.status_code = 200
            page = ProfilePage()
            qtbot.add_widget(page)
            assert page._profiles == [SAMPLE_PROFILE]
            assert page._switcher_widget.isVisible()
            assert page._empty_widget.isVisible() is False
            assert page._form_container.isVisible()

    def test_selecting_profile_loads_form(self, qtbot: QtBot) -> None:
        with patch.object(httpx, "get") as mock_get:
            def get_side_effect(url, **kwargs):
                class MockResp:
                    status_code = 200
                    def raise_for_status(self):
                        pass
                    def json(self):
                        if "users/" in url:
                            return [SAMPLE_PROFILE]
                        return SAMPLE_PROFILE
                return MockResp()
            mock_get.side_effect = get_side_effect
            page = ProfilePage()
            qtbot.add_widget(page)
            # The first profile should be loaded automatically
            assert page._active_profile_id == "p1"
            if page._profile_form:
                assert page._profile_form._display_name.text() == "Om"

    def test_new_profile_card_present_in_switcher(self, qtbot: QtBot) -> None:
        with patch.object(httpx, "get") as mock_get:
            resp = mock_get.return_value
            resp.json.return_value = [SAMPLE_PROFILE]
            resp.raise_for_status.return_value = None
            resp.status_code = 200
            page = ProfilePage()
            qtbot.add_widget(page)
            assert page._new_profile_card is not None
            assert page._new_profile_card.isEnabled()

    def test_new_profile_card_disabled_at_limit(self, qtbot: QtBot) -> None:
        profiles = [
            {**SAMPLE_PROFILE, "id": f"p{i}", "name": f"Profile {i}"}
            for i in range(MAX_PROFILES)
        ]
        with patch.object(httpx, "get") as mock_get:
            resp = mock_get.return_value
            resp.json.return_value = profiles
            resp.raise_for_status.return_value = None
            resp.status_code = 200
            page = ProfilePage()
            qtbot.add_widget(page)
            assert page._new_profile_card is not None
            assert page._new_profile_card.isEnabled() is False

    def test_profile_deleted_from_list(self, qtbot: QtBot) -> None:
        with patch.object(httpx, "get") as mock_get:
            resp = mock_get.return_value
            resp.json.return_value = [SAMPLE_PROFILE, SAMPLE_PROFILE_2]
            resp.raise_for_status.return_value = None
            resp.status_code = 200
            page = ProfilePage()
            qtbot.add_widget(page)
            assert len(page._profiles) == 2
            page._on_profile_deleted("p1")
            assert len(page._profiles) == 1
            assert page._profiles[0]["id"] == "p2"

    def test_upload_resume_picks_file(self, qtbot: QtBot) -> None:
        """Upload button opens file dialog (mocked) and calls parse endpoint."""
        with patch.object(httpx, "get") as mock_get:
            resp = mock_get.return_value
            resp.json.return_value = []
            resp.raise_for_status.return_value = None
            resp.status_code = 200
            page = ProfilePage()
            qtbot.add_widget(page)

        with patch("frontend.pages.profile.QFileDialog.getOpenFileName") as mock_file:
            mock_file.return_value = ("/tmp/test.tex", "")
            with patch.object(httpx, "post") as mock_post:
                post_resp = mock_post.return_value
                post_resp.json.return_value = {
                    "skills": ["Python"],
                    "education": [],
                    "experience": [],
                    "projects": [],
                }
                post_resp.raise_for_status.return_value = None
                post_resp.status_code = 200

                page._on_upload_resume()

                # After upload, form should be in create mode with parsed data
                assert page._form_container.isVisible()
                if page._profile_form:
                    assert "Python" in page._profile_form._skills.get_tags()
