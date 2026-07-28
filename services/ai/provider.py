"""Abstract AI provider interface."""

from __future__ import annotations

from abc import ABC, abstractmethod

from services.ai.models import AIResponse, ModelConfig


class AIProvider(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable provider name."""

    async def supported_models(self) -> list[str]:
        return []

    @property
    @abstractmethod
    def default_model(self) -> str:
        """Default model string for this provider, used as fallback when the
        caller-supplied model was written for a different provider."""

    @abstractmethod
    async def generate(
        self,
        messages: list[dict[str, str]],
        config: ModelConfig | None = None,
    ) -> AIResponse:
        """Send messages to the model and return a response."""

    async def count_tokens(self, text: str) -> int:
        """Count tokens in text. Override for provider-specific counting."""
        return len(text) // 4
