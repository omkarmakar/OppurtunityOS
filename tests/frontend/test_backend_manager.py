"""Tests for BackendManager — lifecycle of the backend child process."""

from __future__ import annotations

import subprocess
from unittest.mock import MagicMock, patch

import pytest

from frontend.backend_manager import BackendManager


# ── is_backend_healthy ───────────────────────────────────────────────


class TestIsBackendHealthy:
    def test_healthy_returns_true(self) -> None:
        manager = BackendManager()
        with patch("httpx.get") as mock_get:
            mock_get.return_value.status_code = 200
            assert manager.is_backend_healthy() is True

    def test_non_200_returns_false(self) -> None:
        manager = BackendManager()
        with patch("httpx.get") as mock_get:
            mock_get.return_value.status_code = 500
            assert manager.is_backend_healthy() is False

    def test_connection_error_returns_false(self) -> None:
        manager = BackendManager()
        with patch("httpx.get") as mock_get:
            mock_get.side_effect = ConnectionError("refused")
            assert manager.is_backend_healthy() is False

    def test_timeout_returns_false(self) -> None:
        manager = BackendManager()
        with patch("httpx.get") as mock_get:
            mock_get.side_effect = TimeoutError("timeout")
            assert manager.is_backend_healthy() is False


# ── start_backend ────────────────────────────────────────────────────


class TestStartBackend:
    @patch("frontend.backend_manager.subprocess.Popen")
    def test_starts_uvicorn_process(self, mock_popen: MagicMock) -> None:
        mock_proc = MagicMock()
        mock_proc.pid = 12345
        mock_proc.poll.return_value = None
        mock_popen.return_value = mock_proc

        manager = BackendManager()
        proc = manager.start_backend()

        assert proc is mock_proc
        assert manager._we_started_it is True

        # Verify the command line
        call_args = mock_popen.call_args
        assert call_args is not None
        args = call_args[0][0]
        assert "-m" in args
        assert "uvicorn" in args
        assert "backend.main:app" in args
        assert "--port" in args
        assert "8000" in args

    @patch("frontend.backend_manager.subprocess.Popen")
    def test_does_not_start_twice(self, mock_popen: MagicMock) -> None:
        mock_proc = MagicMock()
        mock_proc.pid = 12345
        mock_proc.poll.return_value = None
        mock_popen.return_value = mock_proc

        manager = BackendManager()

        # Call start_backend twice
        proc1 = manager.start_backend()
        proc2 = manager.start_backend()

        # Only one Popen call should have been made
        assert mock_popen.call_count == 1
        assert proc1 is proc2
        assert manager._we_started_it is True


# ── ensure_backend_running ───────────────────────────────────────────


class TestEnsureBackendRunning:
    @patch("frontend.backend_manager.subprocess.Popen")
    def test_already_healthy_does_not_spawn(self, mock_popen: MagicMock) -> None:
        manager = BackendManager()
        with patch.object(manager, "is_backend_healthy", return_value=True):
            result = manager.ensure_backend_running()

        assert result is True
        mock_popen.assert_not_called()

    @patch("frontend.backend_manager.subprocess.Popen")
    def test_starts_and_waits_until_healthy(self, mock_popen: MagicMock) -> None:
        mock_proc = MagicMock()
        mock_proc.pid = 12345
        mock_proc.poll.return_value = None
        mock_popen.return_value = mock_proc

        manager = BackendManager()
        # First health check fails, second succeeds
        health_calls: list[bool] = [False, True]

        with patch.object(manager, "is_backend_healthy", side_effect=lambda: health_calls.pop(0)):
            result = manager.ensure_backend_running()

        assert result is True
        mock_popen.assert_called_once()
        assert manager._we_started_it is True

    @patch("frontend.backend_manager.subprocess.Popen")
    def test_timeout_returns_false(self, mock_popen: MagicMock) -> None:
        mock_proc = MagicMock()
        mock_proc.pid = 12345
        mock_proc.poll.return_value = None
        mock_popen.return_value = mock_proc

        manager = BackendManager()
        # Always unhealthy
        with patch.object(manager, "is_backend_healthy", return_value=False):
            with patch("frontend.backend_manager._START_TIMEOUT_S", 0.01):
                with patch("frontend.backend_manager._START_POLL_INTERVAL_S", 0.01):
                    result = manager.ensure_backend_running()

        assert result is False
        mock_popen.assert_called_once()

    @patch("frontend.backend_manager.subprocess.Popen")
    def test_process_exits_early_returns_false(self, mock_popen: MagicMock) -> None:
        mock_proc = MagicMock()
        mock_proc.pid = 12345
        # Simulate the process exits with non-zero code
        mock_proc.poll.return_value = 1
        mock_popen.return_value = mock_proc

        manager = BackendManager()
        with patch.object(manager, "is_backend_healthy", return_value=False):
            with patch("frontend.backend_manager._START_POLL_INTERVAL_S", 0.01):
                result = manager.ensure_backend_running()

        assert result is False

    @patch("frontend.backend_manager.subprocess.Popen")
    def test_process_not_leaked_on_timeout(self, mock_popen: MagicMock) -> None:
        mock_proc = MagicMock()
        mock_proc.pid = 12345
        mock_proc.poll.return_value = None
        mock_popen.return_value = mock_proc

        manager = BackendManager()
        with patch.object(manager, "is_backend_healthy", return_value=False):
            with patch("frontend.backend_manager._START_TIMEOUT_S", 0.01):
                with patch("frontend.backend_manager._START_POLL_INTERVAL_S", 0.01):
                    manager.ensure_backend_running()

        # The process handle should still be tracked even after timeout
        assert manager._process is not None


# ── stop_backend ─────────────────────────────────────────────────────


class TestStopBackend:
    def test_does_nothing_if_not_owner(self) -> None:
        """stop_backend should not touch a process it didn't start."""
        manager = BackendManager()
        manager._process = MagicMock()
        manager._we_started_it = False
        manager.stop_backend()
        # Should not call terminate on a process it doesn't own
        manager._process.terminate.assert_not_called()

    def test_does_nothing_if_already_exited(self) -> None:
        manager = BackendManager()
        mock_proc = MagicMock()
        mock_proc.poll.return_value = 0  # already exited
        manager._process = mock_proc
        manager._we_started_it = True
        manager.stop_backend()
        mock_proc.terminate.assert_not_called()
        assert manager._process is None

    def test_terminates_self_started_process(self) -> None:
        manager = BackendManager()
        mock_proc = MagicMock()
        mock_proc.pid = 12345
        mock_proc.poll.return_value = None  # still running
        # wait() needs to succeed
        mock_proc.wait.return_value = None

        manager._process = mock_proc
        manager._we_started_it = True

        manager.stop_backend()
        mock_proc.terminate.assert_called_once()
        mock_proc.wait.assert_called_once_with(timeout=5.0)
        assert manager._process is None
        assert manager._we_started_it is False

    def test_kills_if_terminate_times_out(self) -> None:
        manager = BackendManager()
        mock_proc = MagicMock()
        mock_proc.pid = 12345
        mock_proc.poll.return_value = None
        mock_proc.wait.side_effect = [
            subprocess.TimeoutExpired("cmd", 5),
            None,
        ]

        manager._process = mock_proc
        manager._we_started_it = True

        manager.stop_backend()
        mock_proc.terminate.assert_called_once()
        mock_proc.kill.assert_called_once()
        assert manager._process is None
        assert manager._we_started_it is False


# ──── factory / constructor ──────────────────────────────────────────


class TestBackendConstructor:
    def test_default_port(self) -> None:
        m = BackendManager()
        assert m._port == 8000

    def test_custom_port(self) -> None:
        m = BackendManager(port=9000)
        assert m._port == 9000
        assert m._process is None
        assert m._we_started_it is False
