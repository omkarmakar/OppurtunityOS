"""Tests for the Settings page."""

from __future__ import annotations

from unittest.mock import patch

import httpx
from pytestqt.qtbot import QtBot

from frontend.pages.settings import SettingsPage


class TestSettingsPage:
    def test_title(self, qtbot: QtBot) -> None:
        page = SettingsPage()
        qtbot.add_widget(page)
        assert page._title == "Settings"

    def test_widget_structure(self, qtbot: QtBot) -> None:
        page = SettingsPage()
        qtbot.add_widget(page)
        assert page._theme_combo is not None
        assert page._lang_combo is not None
        assert page._notif_check is not None
        assert page._sp_combo is not None
        assert page._queries_spin is not None
        assert page._results_spin is not None
        assert page._save_btn is not None
        assert page._save_status is not None

    def test_default_theme(self, qtbot: QtBot) -> None:
        page = SettingsPage()
        qtbot.add_widget(page)
        assert page._theme_combo.currentText() == "system"

    def test_default_language(self, qtbot: QtBot) -> None:
        page = SettingsPage()
        qtbot.add_widget(page)
        assert page._lang_combo.currentText() == "en"

    def test_notifications_enabled_by_default(self, qtbot: QtBot) -> None:
        page = SettingsPage()
        qtbot.add_widget(page)
        assert page._notif_check.isChecked()

    def test_default_sp(self, qtbot: QtBot) -> None:
        page = SettingsPage()
        qtbot.add_widget(page)
        assert page._sp_combo.currentText() == "tavily"

    def test_default_queries(self, qtbot: QtBot) -> None:
        page = SettingsPage()
        qtbot.add_widget(page)
        assert page._queries_spin.value() == 5

    def test_default_results(self, qtbot: QtBot) -> None:
        page = SettingsPage()
        qtbot.add_widget(page)
        assert page._results_spin.value() == 10

    def test_render_integrations_with_data(self, qtbot: QtBot) -> None:
        page = SettingsPage()
        qtbot.add_widget(page)
        page._system_settings = {
            "configuration_status": [
                {"name": "tavily", "configured": True, "env_var": "OOS_TAVILY__API_KEY", "hint": ""},
                {"name": "openai", "configured": False, "env_var": "OOS_AI__OPENAI_API_KEY", "hint": "Get a key"},
            ],
        }
        page._render_integrations()
        assert page._integration_container.count() > 0

    def test_save_preferences_success(self, qtbot: QtBot) -> None:
        page = SettingsPage()
        qtbot.add_widget(page)
        with patch.object(httpx, "put") as mock_put:
            mock_response = mock_put.return_value
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "theme": "dark", "language": "en", "notifications_enabled": True,
                "default_search_provider": "dummy", "default_max_queries": 5,
                "default_max_results": 10,
            }
            page._save_preferences()
            assert page._save_status.text() == "Saved"

    def test_save_preferences_http_error(self, qtbot: QtBot) -> None:
        page = SettingsPage()
        qtbot.add_widget(page)
        with patch.object(httpx, "put") as mock_put:
            mock_response = mock_put.return_value
            mock_response.status_code = 500
            page._save_preferences()
            assert "Error" in page._save_status.text()

    def test_save_preferences_network_error(self, qtbot: QtBot) -> None:
        page = SettingsPage()
        qtbot.add_widget(page)
        with patch.object(httpx, "put") as mock_put:
            mock_put.side_effect = Exception("Connection refused")
            page._save_preferences()
            assert "unreachable" in page._save_status.text()
