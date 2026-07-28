"""Tests for the Profile page (slot-based switcher + TargetingForm + parsed data)."""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import patch

import httpx
import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QMainWindow
from pytestqt.qtbot import QtBot

from frontend.pages.profile import (
    MAX_SLOTS,
    NewSlotCard,
    ProfilePage,
    SectionCard,
    SlotCard,
    _render_education,
    _render_experience,
    _render_projects,
    _render_skills,
)
from frontend.widgets.profile_form import TargetingForm

SAMPLE_SLOT = {
    "id": "s1",
    "user_id": "u1",
    "name": "AI/ML Track",
    "display_name": None,
    "bio": None,
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
    "resume_filename": None,
    "remote_preference": "remote",
    "created_at": "2026-01-01T00:00:00",
    "updated_at": "2026-01-01T00:00:00",
}

SAMPLE_SLOT_2 = {**SAMPLE_SLOT, "id": "s2", "name": "R&D Track"}
SAMPLE_SLOT_3 = {**SAMPLE_SLOT, "id": "s3", "name": "Data Science"}


def _mock_get(json_data, status_code=200):
    m = patch.object(httpx, "get")
    mr = m.start()
    resp = mr.return_value
    resp.json.return_value = json_data
    resp.raise_for_status.return_value = None
    resp.status_code = status_code
    return m


class TestTargetingForm:
    def test_widget_structure(self, qtbot: QtBot) -> None:
        form = TargetingForm()
        qtbot.add_widget(form)
        assert form._name is not None
        assert form._locations is not None
        assert form._remote is not None
        assert form._salary is not None
        assert form._companies is not None
        assert form._save_btn is not None

    def test_populate_and_collect(self, qtbot: QtBot) -> None:
        form = TargetingForm()
        qtbot.add_widget(form)
        form.populate(SAMPLE_SLOT)
        assert form._name.text() == "AI/ML Track"
        assert form._salary.text() == "150k"
        assert form._remote.currentText() == "remote"
        assert "SF" in form._locations.get_tags()
        data = form.collect()
        assert data["name"] == "AI/ML Track"
        assert data["salary_expectations"] == "150k"
        assert data["remote_preference"] == "remote"
        assert "SF" in data["preferred_locations"]

    def test_clear(self, qtbot: QtBot) -> None:
        form = TargetingForm()
        qtbot.add_widget(form)
        form.populate(SAMPLE_SLOT)
        form.clear()
        assert form._name.text() == ""
        assert form._salary.text() == ""
        assert form._locations.get_tags() == []
        assert form._companies.get_tags() == []
        assert form._remote.currentIndex() == 0
        assert form.get_slot_id() is None

    def test_set_slot_id(self, qtbot: QtBot) -> None:
        form = TargetingForm()
        qtbot.add_widget(form)
        assert form.get_slot_id() is None
        form.set_slot_id("s1")
        assert form.get_slot_id() == "s1"

    def test_collect_empty_returns_empty(self, qtbot: QtBot) -> None:
        form = TargetingForm()
        qtbot.add_widget(form)
        data = form.collect()
        assert data == {}


class TestSlotCard:
    def test_creation(self, qtbot: QtBot) -> None:
        card = SlotCard(SAMPLE_SLOT, active=True)
        qtbot.add_widget(card)
        assert card._slot_id == "s1"

    def test_subtitle_from_skills(self, qtbot: QtBot) -> None:
        card = SlotCard(SAMPLE_SLOT)
        qtbot.add_widget(card)
        assert "Python" in card._derive_subtitle(SAMPLE_SLOT)

    def test_subtitle_from_locations(self, qtbot: QtBot) -> None:
        data = {**SAMPLE_SLOT, "skills": []}
        card = SlotCard(data)
        qtbot.add_widget(card)
        assert "SF" in card._derive_subtitle(data)

    def test_subtitle_fallback(self, qtbot: QtBot) -> None:
        data = {**SAMPLE_SLOT, "skills": [], "preferred_locations": []}
        card = SlotCard(data)
        qtbot.add_widget(card)
        assert card._derive_subtitle(data) == "No details yet"


class TestNewSlotCard:
    def test_enabled_by_default(self, qtbot: QtBot) -> None:
        card = NewSlotCard()
        qtbot.add_widget(card)
        assert card.isEnabled() is True
        assert card.toolTip() == ""

    def test_disabled_at_limit(self, qtbot: QtBot) -> None:
        card = NewSlotCard()
        qtbot.add_widget(card)
        card.set_disabled(True)
        assert card.isEnabled() is False
        assert f"{MAX_SLOTS}" in card.toolTip()


class TestSectionCard:
    def test_creation(self, qtbot: QtBot) -> None:
        card = SectionCard("Skills")
        qtbot.add_widget(card)
        assert card._layout is not None


class TestRenderHelpers:
    def test_render_skills(self, qtbot: QtBot) -> None:
        from PySide6.QtWidgets import QVBoxLayout, QWidget

        w = QWidget()
        qtbot.add_widget(w)
        layout = QVBoxLayout(w)
        _render_skills(layout, ["Python", "Go"])
        assert layout.count() == 1

    def test_render_education(self, qtbot: QtBot) -> None:
        from PySide6.QtWidgets import QVBoxLayout, QWidget

        w = QWidget()
        qtbot.add_widget(w)
        layout = QVBoxLayout(w)
        _render_education(layout, [{"institution": "MIT", "degree": "B.S.", "field": "CS"}])
        assert layout.count() == 1

    def test_render_experience(self, qtbot: QtBot) -> None:
        from PySide6.QtWidgets import QVBoxLayout, QWidget

        w = QWidget()
        qtbot.add_widget(w)
        layout = QVBoxLayout(w)
        _render_experience(layout, [{"company": "Google", "role": "SWE", "description": "Built stuff"}])
        assert layout.count() == 1

    def test_render_projects(self, qtbot: QtBot) -> None:
        from PySide6.QtWidgets import QVBoxLayout, QWidget

        w = QWidget()
        qtbot.add_widget(w)
        layout = QVBoxLayout(w)
        _render_projects(layout, [{"name": "MyApp", "technologies": "Python"}])
        assert layout.count() == 1

    def test_render_empty_skills_skips(self, qtbot: QtBot) -> None:
        from PySide6.QtWidgets import QVBoxLayout, QWidget

        w = QWidget()
        qtbot.add_widget(w)
        layout = QVBoxLayout(w)
        _render_skills(layout, [])
        assert layout.count() == 0


class TestProfilePage:
    def test_title(self, qtbot: QtBot) -> None:
        page = ProfilePage()
        window = QMainWindow()
        window.setCentralWidget(page)
        qtbot.add_widget(window)
        qtbot.wait(50)
        assert page._title == "Profile"
        window.close()

    def test_empty_state_shown_when_no_slots(self, qtbot: QtBot) -> None:
        with patch.object(httpx, "get") as mock_get:
            resp = mock_get.return_value
            resp.json.return_value = []
            resp.raise_for_status.return_value = None
            resp.status_code = 200
            page = ProfilePage()
            window = QMainWindow()
            window.setCentralWidget(page)
            qtbot.add_widget(window)
            window.show()
            qtbot.wait(50)
            assert page._empty_widget.isVisible()
            assert page._switcher_widget.isVisible() is False
            assert page._content_area.isVisible() is False
            window.close()

    def test_switcher_shown_when_slots_exist(self, qtbot: QtBot) -> None:
        with patch.object(httpx, "get") as mock_get:
            def get_side_effect(url, **kwargs):
                class MockResp:
                    status_code = 200
                    def raise_for_status(self):
                        pass
                    def json(self):
                        if "profiles/id/" in url:
                            return SAMPLE_SLOT
                        return [SAMPLE_SLOT]
                return MockResp()
            mock_get.side_effect = get_side_effect
            page = ProfilePage()
            window = QMainWindow()
            window.setCentralWidget(page)
            qtbot.add_widget(window)
            window.show()
            qtbot.wait(50)
            assert page._slots == [SAMPLE_SLOT]
            assert page._switcher_widget.isVisible()
            assert page._empty_widget.isVisible() is False
            assert page._content_area.isVisible()
            window.close()

    def test_selecting_slot_loads_view(self, qtbot: QtBot) -> None:
        with patch.object(httpx, "get") as mock_get:
            def get_side_effect(url, **kwargs):
                class MockResp:
                    status_code = 200
                    def raise_for_status(self):
                        pass
                    def json(self):
                        if "users/" in url:
                            return [SAMPLE_SLOT]
                        return SAMPLE_SLOT
                return MockResp()
            mock_get.side_effect = get_side_effect
            page = ProfilePage()
            window = QMainWindow()
            window.setCentralWidget(page)
            qtbot.add_widget(window)
            window.show()
            qtbot.wait(50)
            assert page._active_slot_id == "s1"
            if page._targeting_form:
                assert page._targeting_form._name.text() == "AI/ML Track"
            window.close()

    def test_new_slot_card_present_in_switcher(self, qtbot: QtBot) -> None:
        with patch.object(httpx, "get") as mock_get:
            def get_side_effect(url, **kwargs):
                class MockResp:
                    status_code = 200
                    def raise_for_status(self):
                        pass
                    def json(self):
                        if "profiles/id/" in url:
                            return SAMPLE_SLOT
                        return [SAMPLE_SLOT]
                return MockResp()
            mock_get.side_effect = get_side_effect
            page = ProfilePage()
            window = QMainWindow()
            window.setCentralWidget(page)
            qtbot.add_widget(window)
            window.show()
            qtbot.wait(50)
            assert page._new_slot_card is not None
            assert page._new_slot_card.isEnabled()
            window.close()

    def test_new_slot_card_disabled_at_limit(self, qtbot: QtBot) -> None:
        slots = [
            {**SAMPLE_SLOT, "id": f"s{i}", "name": f"Slot {i}"}
            for i in range(MAX_SLOTS)
        ]
        with patch.object(httpx, "get") as mock_get:
            def get_side_effect(url, **kwargs):
                class MockResp:
                    status_code = 200
                    def raise_for_status(self):
                        pass
                    def json(self):
                        if "profiles/id/" in url:
                            return slots[0]
                        return slots
                return MockResp()
            mock_get.side_effect = get_side_effect
            page = ProfilePage()
            window = QMainWindow()
            window.setCentralWidget(page)
            qtbot.add_widget(window)
            window.show()
            qtbot.wait(50)
            assert page._new_slot_card is not None
            assert page._new_slot_card.isEnabled() is False
            window.close()

    def test_upload_resume_picks_file(self, qtbot: QtBot) -> None:
        tmp = tempfile.NamedTemporaryFile(suffix=".tex", delete=False)
        tmp.write(b"\\documentclass{article}\\begin{document}Test\\end{document}")
        tmp.close()
        tmp_path = tmp.name

        try:
            with patch.object(httpx, "get") as mock_get:
                resp = mock_get.return_value
                resp.json.return_value = []
                resp.raise_for_status.return_value = None
                resp.status_code = 200
                page = ProfilePage()
                window = QMainWindow()
                window.setCentralWidget(page)
                qtbot.add_widget(window)
                window.show()

            with patch("frontend.pages.profile.QFileDialog.getOpenFileName") as mock_file:
                mock_file.return_value = (tmp_path, "")
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

                    qtbot.wait(50)
                    assert page._targeting_form is not None
                    assert page._targeting_form._name.text() == "Python Track"
                    assert page._targeting_form.get_slot_id() is None
                window.close()
        finally:
            Path(tmp_path).unlink(missing_ok=True)
