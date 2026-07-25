"""Abstract pipeline step."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class PipelineStep(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable step name."""

    @abstractmethod
    async def execute(self, ctx: dict[str, Any]) -> dict[str, Any]:
        """Execute this step, reading from and writing to the shared context dict."""
