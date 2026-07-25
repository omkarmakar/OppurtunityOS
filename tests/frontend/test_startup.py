"""Tests for Windows startup registration utility."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from frontend.utils.startup import APP_NAME, is_registered, register, unregister


class TestWindowsStartup:
    """Test suite for startup registry helpers."""

    @patch("frontend.utils.startup.winreg")  # noqa: TID251
    def test_register_success(self, mock_winreg: MagicMock) -> None:
        mock_key = MagicMock()
        mock_winreg.OpenKey.return_value = mock_key
        result = register()
        assert result is True
        mock_winreg.SetValueEx.assert_called_once()

    @patch("frontend.utils.startup.winreg")  # noqa: TID251
    def test_unregister_success(self, mock_winreg: MagicMock) -> None:
        mock_key = MagicMock()
        mock_winreg.OpenKey.return_value = mock_key
        result = unregister()
        assert result is True
        mock_winreg.DeleteValue.assert_called_once()

    @patch("frontend.utils.startup.winreg")  # noqa: TID251
    def test_is_registered_true(self, mock_winreg: MagicMock) -> None:
        mock_key = MagicMock()
        mock_winreg.OpenKey.return_value = mock_key
        expected_cmd = f'"{__import__("sys").executable}" -m frontend.main'
        mock_winreg.QueryValueEx.return_value = (expected_cmd, 1)
        assert is_registered() is True

    @patch("frontend.utils.startup.winreg")  # noqa: TID251
    def test_is_registered_false(self, mock_winreg: MagicMock) -> None:
        mock_key = MagicMock()
        mock_winreg.OpenKey.return_value = mock_key
        mock_winreg.QueryValueEx.side_effect = OSError("not found")
        assert is_registered() is False

    @patch("frontend.utils.startup.winreg")  # noqa: TID251
    def test_register_sets_correct_value(self, mock_winreg: MagicMock) -> None:
        mock_key = MagicMock()
        mock_winreg.OpenKey.return_value = mock_key
        register()
        expected = f'"{__import__("sys").executable}" -m frontend.main'
        mock_winreg.SetValueEx.assert_called_once_with(mock_key, APP_NAME, 0, mock_winreg.REG_SZ, expected)

    @patch("frontend.utils.startup.winreg")  # noqa: TID251
    def test_register_oserror_returns_false(self, mock_winreg: MagicMock) -> None:
        mock_winreg.OpenKey.side_effect = OSError("Access denied")
        result = register()
        assert result is False

    def test_app_name_is_correct(self) -> None:
        assert APP_NAME == "OpportunityOS"

    @patch("frontend.utils.startup.winreg", None)  # noqa: TID251
    def test_no_winreg_fallback(self) -> None:
        assert register() is False
        assert unregister() is False
        assert is_registered() is False
