"""Pipeline notification interface and implementations."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class PipelineEvent:
    step: str = ""
    status: str = ""  # started, progress, completed, failed
    message: str = ""
    data: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class PipelineNotifier(ABC):
    @abstractmethod
    def on_event(self, event: PipelineEvent) -> None:
        """Handle a pipeline event."""


class LoggingNotifier(PipelineNotifier):
    def on_event(self, event: PipelineEvent) -> None:
        prefix = f"[{event.timestamp.isoformat()}] {event.step}: {event.status}"
        print(f"{prefix} — {event.message}")


class CallbackNotifier(PipelineNotifier):
    def __init__(
        self,
        callback: Any = None,
    ) -> None:
        self._callback = callback

    def on_event(self, event: PipelineEvent) -> None:
        if self._callback:
            self._callback(event)
