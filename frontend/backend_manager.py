"""Manages the backend server as a child process of the frontend.

Ensures the backend (uvicorn serving ``backend.main:app``) is running
before the GUI makes any API calls.  On Windows startup the frontend is
already auto-launched; this makes the backend transitively start too,
fixing the root cause of the scheduler/digest pipeline never running
unattended.
"""

from __future__ import annotations

import logging
import os
import platform
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_BACKEND_PORT = 8000
_HEALTH_URL = f"http://127.0.0.1:{_BACKEND_PORT}/api/v1/health"
_HEALTH_TIMEOUT_S = 2.0
_START_POLL_INTERVAL_S = 0.5
_START_TIMEOUT_S = 15.0


class BackendManager:
    """Manages the lifecycle of the backend uvicorn process.

    Only kills the process if *this instance* started it — never touches
    an independently-running backend (e.g. dev script).
    """

    def __init__(self, port: int = _BACKEND_PORT) -> None:
        self._port = port
        self._process: subprocess.Popen[bytes] | None = None
        self._we_started_it = False
        self._log_dir: str | None = None

    # ── public API ───────────────────────────────────────────────────

    def is_backend_healthy(self) -> bool:
        """Quick health-check against the backend."""
        import httpx

        try:
            resp = httpx.get(
                f"http://127.0.0.1:{self._port}/api/v1/health",
                timeout=_HEALTH_TIMEOUT_S,
            )
            return resp.status_code == 200
        except Exception:
            return False

    def start_backend(self) -> subprocess.Popen[bytes] | None:
        """Launch the backend as a detached child process.

        Returns the ``Popen`` handle, or ``None`` if the backend already
        appears to be running (caller should call :meth:`is_backend_healthy`
        first to avoid this).
        """
        if self._process and self._process.poll() is None:
            logger.info("Backend process already running (pid %d)", self._process.pid)
            return self._process

        log_path = self._resolve_log_path()
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_file = log_path.open("ab")

        cmd = [
            sys.executable,
            "-m",
            "uvicorn",
            "backend.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(self._port),
        ]

        startupinfo: Any = None
        creationflags = 0
        if platform.system() == "Windows":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE
            creationflags = subprocess.CREATE_NO_WINDOW

        logger.info("Starting backend: %s  (log: %s)", " ".join(cmd), log_path)
        self._process = subprocess.Popen(
            cmd,
            stdout=log_file,
            stderr=log_file,
            startupinfo=startupinfo,
            creationflags=creationflags,
        )
        self._we_started_it = True
        logger.info("Backend started (pid %d)", self._process.pid)
        return self._process

    def ensure_backend_running(self) -> bool:
        """Check health; if unhealthy, spawn and wait for readiness.

        Returns ``True`` if the backend became healthy within the timeout,
        ``False`` otherwise.
        """
        if self.is_backend_healthy():
            logger.info("Backend already healthy")
            return True

        self.start_backend()
        deadline = time.monotonic() + _START_TIMEOUT_S

        while time.monotonic() < deadline:
            time.sleep(_START_POLL_INTERVAL_S)
            if self.is_backend_healthy():
                logger.info("Backend is now healthy after startup")
                return True
            if self._process and self._process.poll() is not None:
                logger.warning("Backend process exited prematurely (rc %d)", self._process.returncode)
                return False

        logger.warning("Backend did not become healthy within %.1f s", _START_TIMEOUT_S)
        return False

    def stop_backend(self) -> None:
        """Terminate the backend process, but only if we started it."""
        if not self._we_started_it:
            logger.info("Not stopping backend — we did not start it")
            return
        if self._process is None:
            return
        if self._process.poll() is not None:
            logger.info("Backend already exited (rc %d)", self._process.returncode)
            self._process = None
            return

        logger.info("Stopping backend (pid %d)", self._process.pid)
        self._process.terminate()
        try:
            self._process.wait(timeout=5.0)
        except subprocess.TimeoutExpired:
            logger.warning("Backend did not terminate gracefully, killing")
            self._process.kill()
            self._process.wait(timeout=2.0)
        self._process = None
        self._we_started_it = False

    # ── helpers ──────────────────────────────────────────────────────

    def _resolve_log_path(self) -> Path:
        """Return the filesystem path for backend log output."""
        if self._log_dir:
            base = Path(self._log_dir)
        else:
            from core.config import get_config
            cfg = get_config()
            base = Path(cfg.paths.log_dir)
        return base / "backend.log"
