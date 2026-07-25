"""Tests for the Bookmarks page."""

from __future__ import annotations

from unittest.mock import patch

import httpx
from pytestqt.qtbot import QtBot

from frontend.pages.bookmarks import BookmarksPage


class TestBookmarksPage:
    def test_title(self, qtbot: QtBot) -> None:
        page = BookmarksPage()
        qtbot.add_widget(page)
        assert page._title == "Bookmarks"

    def test_widget_structure(self, qtbot: QtBot) -> None:
        page = BookmarksPage()
        qtbot.add_widget(page)
        assert page._prev_btn is not None
        assert page._next_btn is not None
        assert page._page_label is not None

    def test_default_page(self, qtbot: QtBot) -> None:
        page = BookmarksPage()
        qtbot.add_widget(page)
        assert page._page == 1
        assert page._page_size == 10

    def test_offline_render_on_http_error(self, qtbot: QtBot) -> None:
        page = BookmarksPage()
        qtbot.add_widget(page)
        with patch.object(httpx, "get") as mock_get:
            mock_get.side_effect = Exception("Connection refused")
            page._load_data()
        assert page._result_count_label.text() == "Offline"

    def test_empty_state(self, qtbot: QtBot) -> None:
        page = BookmarksPage()
        qtbot.add_widget(page)
        with patch.object(httpx, "get") as mock_get:
            mock_response = mock_get.return_value
            mock_response.raise_for_status.return_value = None
            mock_response.json.return_value = {"items": [], "total": 0, "page": 1, "page_size": 10}
            page._load_data()
        assert page._result_count_label.text() == "0 total"

    def test_pagination_disabled_on_empty(self, qtbot: QtBot) -> None:
        page = BookmarksPage()
        qtbot.add_widget(page)
        with patch.object(httpx, "get") as mock_get:
            mock_response = mock_get.return_value
            mock_response.raise_for_status.return_value = None
            mock_response.json.return_value = {"items": [], "total": 0, "page": 1, "page_size": 10}
            page._load_data()
        assert not page._next_btn.isEnabled()
        assert not page._prev_btn.isEnabled()

    def test_pagination_enabled_with_items(self, qtbot: QtBot) -> None:
        page = BookmarksPage()
        qtbot.add_widget(page)
        with patch.object(httpx, "get") as mock_get:
            mock_response = mock_get.return_value
            mock_response.raise_for_status.return_value = None
            mock_response.json.return_value = {
                "items": [{"id": "1", "opportunity_title": "Test", "relevance_score": 80}],
                "total": 25,
                "page": 1,
                "page_size": 10,
            }
            page._load_data()
        assert page._next_btn.isEnabled()
        assert not page._prev_btn.isEnabled()
