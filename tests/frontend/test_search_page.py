"""Tests for the Search page."""

from __future__ import annotations

from unittest.mock import patch

import httpx
from pytestqt.qtbot import QtBot

from frontend.pages.search import SearchPage


class TestSearchPage:
    def test_title(self, qtbot: QtBot) -> None:
        page = SearchPage()
        qtbot.add_widget(page)
        assert page._title == "Search"

    def test_widget_structure(self, qtbot: QtBot) -> None:
        page = SearchPage()
        qtbot.add_widget(page)
        assert page._provider_combo is not None
        assert page._queries_spin is not None
        assert page._results_spin is not None
        assert page._skip_rank_check is not None
        assert page._run_btn is not None
        assert page._progress is not None

    def test_default_values(self, qtbot: QtBot) -> None:
        page = SearchPage()
        qtbot.add_widget(page)
        assert page._queries_spin.value() == 5
        assert page._results_spin.value() == 10
        assert page._skip_rank_check.isChecked() is False
        assert page._is_running is False

    def test_combo_empty_until_loaded(self, qtbot: QtBot) -> None:
        with patch.object(httpx, "get") as mock_get:
            mock_response = mock_get.return_value
            mock_response.json.return_value = [{"name": "dummy"}]
            mock_response.raise_for_status.return_value = None
            mock_response.status_code = 200
            page = SearchPage()
            qtbot.add_widget(page)
            assert page._provider_combo.count() == 0
            qtbot.wait(50)
            assert page._provider_combo.count() == 1
            assert page._provider_combo.currentText() == "dummy"

    def test_combo_fallback_on_http_error(self, qtbot: QtBot) -> None:
        with patch.object(httpx, "get") as mock_get:
            mock_get.side_effect = Exception("Connection refused")
            page = SearchPage()
            qtbot.add_widget(page)
            qtbot.wait(50)
            assert page._provider_combo.count() >= 1

    def test_progress_hidden_initially(self, qtbot: QtBot) -> None:
        page = SearchPage()
        qtbot.add_widget(page)
        assert page._progress.isHidden()

    def test_results_card_hidden_initially(self, qtbot: QtBot) -> None:
        page = SearchPage()
        qtbot.add_widget(page)
        assert page._results_card.isHidden()

    def test_run_button_enabled_initially(self, qtbot: QtBot) -> None:
        page = SearchPage()
        qtbot.add_widget(page)
        assert page._run_btn.isEnabled()

    def test_run_button_styled_as_primary(self, qtbot: QtBot) -> None:
        page = SearchPage()
        qtbot.add_widget(page)
        style = page._run_btn.styleSheet()
        assert "#7c3aed" in style

    def test_skip_ranking_unchecked_by_default(self, qtbot: QtBot) -> None:
        page = SearchPage()
        qtbot.add_widget(page)
        assert not page._skip_rank_check.isChecked()

    def test_last_run_hidden_initially(self, qtbot: QtBot) -> None:
        page = SearchPage()
        qtbot.add_widget(page)
        assert page._last_run_card.isHidden()
