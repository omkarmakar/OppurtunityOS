"""Notification scheduler — periodically triggers daily digest."""

from __future__ import annotations

import logging
import threading
from datetime import datetime, date
from typing import Any, Callable

logger = logging.getLogger(__name__)


class NotificationScheduler:
    """Daemon-thread scheduler that triggers the daily digest on a configurable schedule."""

    def __init__(
        self,
        digest_callback: Callable[[], dict[str, Any]] | None = None,
        polling_interval: int = 60,
        digest_hour: int = 8,
        digest_minute: int = 0,
    ) -> None:
        self._callback = digest_callback
        self._interval = polling_interval
        self._hour = digest_hour
        self._minute = digest_minute
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._last_digest_date: date | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        logger.info("Scheduler started (polling every %ds, digest at %02d:%02d)", self._interval, self._hour, self._minute)

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("Scheduler stopped")

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                self._check_digest()
            except Exception as exc:
                logger.error("Scheduler error: %s", exc)
            self._stop_event.wait(self._interval)

    def _check_digest(self) -> None:
        now = datetime.now()
        today = now.date()
        if now.hour == self._hour and now.minute == self._minute and self._last_digest_date != today:
            if self._callback:
                result = self._callback()
                logger.info("Digest triggered: %s", result)
                self._last_digest_date = today
