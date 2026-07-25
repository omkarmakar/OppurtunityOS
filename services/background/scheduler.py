"""Background scheduler — runs scheduled tasks with retry and duplicate prevention."""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable

logger = logging.getLogger(__name__)


@dataclass
class ScheduledTask:
    """A task managed by the BackgroundScheduler.

    Attributes:
        name: Unique task identifier.
        interval_seconds: Seconds between runs, or a callable returning int.
        callback: Synchronous callable to execute.
        max_retries: Number of retry attempts on failure (0 = no retry).
        retry_delay_base: Base seconds for exponential backoff (2^attempt * base).
        enabled: Whether this task is eligible to run.
    """
    name: str
    interval_seconds: int | Callable[[], int]
    callback: Callable[[], Any]
    max_retries: int = 3
    retry_delay_base: float = 10.0
    enabled: bool = True
    run_condition: Callable[[], bool] | None = None
    _last_run: datetime | None = field(default=None, repr=False)
    _running: bool = field(default=False, repr=False)


class BackgroundScheduler:
    """Daemon-thread scheduler that manages and runs ScheduledTask instances.

    Features:
    - Polls every N seconds and runs tasks whose interval has elapsed or run_condition is satisfied.
    - Supports callable intervals for dynamic re-reading from config.
    - Prevents duplicate concurrent runs of the same task.
    - Retries failed tasks with exponential backoff.
    """

    def __init__(self, polling_interval: int = 30) -> None:
        self._polling_interval = max(5, polling_interval)
        self._tasks: dict[str, ScheduledTask] = {}
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()

    # ── task management ──────────────────────────────────────────────

    def add_task(self, task: ScheduledTask) -> None:
        """Register a task with the scheduler."""
        with self._lock:
            self._tasks[task.name] = task

    def remove_task(self, name: str) -> None:
        """Unregister a task by name."""
        with self._lock:
            self._tasks.pop(name, None)

    def get_task(self, name: str) -> ScheduledTask | None:
        """Look up a task by name."""
        with self._lock:
            return self._tasks.get(name)

    @property
    def tasks(self) -> list[ScheduledTask]:
        """Return all registered tasks."""
        with self._lock:
            return list(self._tasks.values())

    # ── lifecycle ───────────────────────────────────────────────────

    def start(self) -> None:
        """Start the scheduler background thread (idempotent)."""
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        logger.info("Background scheduler started (polling every %ds)", self._polling_interval)

    def stop(self) -> None:
        """Stop the scheduler background thread."""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("Background scheduler stopped")

    @property
    def running(self) -> bool:
        """Whether the scheduler thread is active."""
        return self._thread is not None and self._thread.is_alive()

    # ── internals ───────────────────────────────────────────────────

    def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                self._tick()
            except Exception as exc:
                logger.error("Scheduler loop error: %s", exc)
            self._stop_event.wait(self._polling_interval)

    def _tick(self) -> None:
        """Check each task and launch overdue ones."""
        now = datetime.now(timezone.utc)
        with self._lock:
            tasks_snapshot = list(self._tasks.values())
        for task in tasks_snapshot:
            if not task.enabled:
                continue
            if task._running:
                continue  # prevent duplicate concurrent runs

            if task.run_condition is not None:
                if not task.run_condition():
                    continue
            else:
                interval = task.interval_seconds() if callable(task.interval_seconds) else task.interval_seconds
                if task._last_run and (now - task._last_run).total_seconds() < interval:
                    continue  # not yet due

            task._running = True
            task._last_run = now
            threading.Thread(
                target=self._run_task_with_retry,
                args=(task,),
                daemon=True,
            ).start()

    def _run_task_with_retry(self, task: ScheduledTask) -> None:
        """Execute a task's callback with exponential-backoff retry."""
        try:
            for attempt in range(task.max_retries + 1):
                try:
                    result = task.callback()
                    if result is not None:
                        logger.info("Task '%s' completed: %s", task.name, result)
                    else:
                        logger.info("Task '%s' completed", task.name)
                    return
                except Exception as exc:
                    if attempt < task.max_retries:
                        delay = task.retry_delay_base * (2 ** attempt)
                        logger.warning(
                            "Task '%s' failed (attempt %d/%d): %s. Retrying in %.1fs",
                            task.name, attempt + 1, task.max_retries + 1, exc, delay,
                        )
                        time.sleep(delay)
                    else:
                        logger.error(
                            "Task '%s' failed after %d attempts: %s",
                            task.name, task.max_retries + 1, exc,
                        )
        finally:
            task._running = False
