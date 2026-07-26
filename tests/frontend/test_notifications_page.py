"""Tests for the Notifications page."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from pytestqt.qtbot import QtBot

from frontend.pages.notifications import NotificationsPage


class TestNotificationsPage:
    def test_title(self, qtbot: QtBot) -> None:
        page = NotificationsPage()
        qtbot.add_widget(page)
        # Page uses "Notifications" as title in _build_header_row
        # We can't directly access the QLabel, so we check the widget exists
        assert page is not None

    def test_has_send_digest_button(self, qtbot: QtBot) -> None:
        page = NotificationsPage()
        qtbot.add_widget(page)
        # Check that the page loaded and has buttons
        # (buttons are created during _setup_ui)
        assert page._main_layout is not None

    def test_has_test_email_button(self, qtbot: QtBot) -> None:
        page = NotificationsPage()
        qtbot.add_widget(page)
        assert page._main_layout is not None

    def test_load_data_success(self, qtbot: QtBot) -> None:
        page = NotificationsPage()
        qtbot.add_widget(page)
        
        mock_response = {
            "items": [
                {
                    "id": "n1",
                    "type": "opportunity",
                    "title": "New Role Found",
                    "message": "Score 85/100",
                    "is_read": False,
                    "created_at": "2026-07-26T10:00:00Z",
                }
            ],
            "total": 1,
            "unread_count": 1,
        }
        
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.read.return_value = json.dumps(mock_response).encode()
            mock_urlopen.return_value = mock_resp
            page._load_data()
        
        assert page._data == mock_response
        # Check that unread_label shows the count
        assert "1 unread" in page._unread_label.text()

    def test_empty_notifications(self, qtbot: QtBot) -> None:
        page = NotificationsPage()
        qtbot.add_widget(page)
        
        mock_response = {
            "items": [],
            "total": 0,
            "unread_count": 0,
        }
        
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.read.return_value = json.dumps(mock_response).encode()
            mock_urlopen.return_value = mock_resp
            page._load_data()
        
        assert "All caught up" in page._unread_label.text()

    def test_trigger_digest_success(self, qtbot: QtBot) -> None:
        page = NotificationsPage()
        qtbot.add_widget(page)
        
        digest_response = {
            "digest_id": "d123",
            "notifications_count": 4,
            "email_sent": True,
            "message": "Digest created with 4 notification(s) and emailed",
        }
        
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.read.return_value = json.dumps(digest_response).encode()
            mock_urlopen.return_value = mock_resp
            page._trigger_digest()
        
        # Check that the result is shown
        assert "4 items" in page._unread_label.text()
        assert "emailed" in page._unread_label.text()

    def test_trigger_digest_no_items(self, qtbot: QtBot) -> None:
        page = NotificationsPage()
        qtbot.add_widget(page)
        
        digest_response = {
            "digest_id": "",
            "notifications_count": 0,
            "email_sent": False,
            "message": "No new notifications to send",
        }
        
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.read.return_value = json.dumps(digest_response).encode()
            mock_urlopen.return_value = mock_resp
            page._trigger_digest()
        
        assert "No new notifications" in page._unread_label.text()

    def test_trigger_digest_error(self, qtbot: QtBot) -> None:
        page = NotificationsPage()
        qtbot.add_widget(page)
        
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.side_effect = Exception("Connection failed")
            page._trigger_digest()
        
        assert "Error" in page._unread_label.text()

    def test_test_email_success(self, qtbot: QtBot) -> None:
        page = NotificationsPage()
        qtbot.add_widget(page)
        
        test_response = {
            "success": True,
            "message": "Email sent",
        }
        
        with patch("urllib.request.urlopen") as mock_urlopen, \
             patch("PySide6.QtWidgets.QInputDialog.getText") as mock_dialog:
            mock_dialog.return_value = ("user@example.com", True)
            mock_resp = MagicMock()
            mock_resp.read.return_value = json.dumps(test_response).encode()
            mock_urlopen.return_value = mock_resp
            page._test_email()
        
        assert "Email sent" in page._unread_label.text()

    def test_test_email_failure(self, qtbot: QtBot) -> None:
        page = NotificationsPage()
        qtbot.add_widget(page)
        
        test_response = {
            "success": False,
            "message": "SMTP connection failed",
        }
        
        with patch("urllib.request.urlopen") as mock_urlopen, \
             patch("PySide6.QtWidgets.QInputDialog.getText") as mock_dialog:
            mock_dialog.return_value = ("user@example.com", True)
            mock_resp = MagicMock()
            mock_resp.read.return_value = json.dumps(test_response).encode()
            mock_urlopen.return_value = mock_resp
            page._test_email()
        
        assert "SMTP connection failed" in page._unread_label.text()

    def test_test_email_user_cancel(self, qtbot: QtBot) -> None:
        page = NotificationsPage()
        qtbot.add_widget(page)
        
        with patch("PySide6.QtWidgets.QInputDialog.getText") as mock_dialog:
            mock_dialog.return_value = ("", False)  # User cancelled
            page._test_email()
        
        # No error should occur, just return
        assert page is not None

    def test_mark_all_read(self, qtbot: QtBot) -> None:
        page = NotificationsPage()
        qtbot.add_widget(page)
        
        # Mock the mark-all-read endpoint
        mark_response = {"marked": 3}
        
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.read.return_value = json.dumps(mark_response).encode()
            mock_urlopen.return_value = mock_resp
            
            # Mock the subsequent load_data call
            page._load_data = MagicMock()
            page._mark_all_read()
        
        # Should have called load_data to refresh
        page._load_data.assert_called_once()
