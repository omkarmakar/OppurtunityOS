"""Tests for the Opportunities page."""

from __future__ import annotations

from unittest.mock import patch

from pytestqt.qtbot import QtBot

from frontend.pages.opportunities import OpportunitiesPage


class TestOpportunitiesPage:
    def test_title(self, qtbot: QtBot) -> None:
        page = OpportunitiesPage()
        qtbot.add_widget(page)
        assert page._title == "Opportunities"

    def test_widget_structure(self, qtbot: QtBot) -> None:
        page = OpportunitiesPage()
        qtbot.add_widget(page)
        assert page._profile_combo is not None
        assert page._status_combo is not None
        assert page._score_spin is not None
        assert page._sort_combo is not None
        assert page._prev_btn is not None
        assert page._next_btn is not None
        assert page._page_label is not None

    def test_default_filters(self, qtbot: QtBot) -> None:
        page = OpportunitiesPage()
        qtbot.add_widget(page)
        assert page._status_combo.currentText() == "All Statuses"
        assert page._score_spin.value() == 0
        assert page._sort_combo.currentText() == "Score"
        assert page._page == 1

    def test_offline_render_on_http_error(self, qtbot: QtBot) -> None:
        page = OpportunitiesPage()
        qtbot.add_widget(page)
        with patch("httpx.get") as mock_get:
            mock_get.side_effect = Exception("Connection refused")
            page._load_data()
        assert page._result_count_label.text() == "Offline"

    def test_empty_state(self, qtbot: QtBot) -> None:
        page = OpportunitiesPage()
        qtbot.add_widget(page)
        with patch("httpx.get") as mock_get:
            mock_response = mock_get.return_value
            mock_response.raise_for_status.return_value = None
            mock_response.json.return_value = {"items": [], "total": 0, "page": 1}
            page._load_data()
        assert page._result_count_label.text() == "0 total"

    def test_pagination_disabled_on_empty(self, qtbot: QtBot) -> None:
        page = OpportunitiesPage()
        qtbot.add_widget(page)
        with patch("httpx.get") as mock_get:
            mock_response = mock_get.return_value
            mock_response.raise_for_status.return_value = None
            mock_response.json.return_value = {"items": [], "total": 0, "page": 1}
            page._load_data()
        assert not page._next_btn.isEnabled()
        assert not page._prev_btn.isEnabled()
