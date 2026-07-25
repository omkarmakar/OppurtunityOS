"""Abstract base service."""

from __future__ import annotations

from abc import ABC, abstractmethod


class BaseService(ABC):
    """Abstract base class for all business logic services."""

    @abstractmethod
    async def execute(self, **kwargs) -> None:
        """Execute the service operation."""
