"""Dummy AI provider for development and testing."""

from __future__ import annotations

from services.ai.models import AIResponse, ModelConfig
from services.ai.provider import AIProvider


class DummyAIProvider(AIProvider):
    @property
    def name(self) -> str:
        return "DummyAI"

    @property
    def supported_models(self) -> list[str]:
        return ["dummy-model"]

    async def generate(
        self,
        messages: list[dict[str, str]],
        config: ModelConfig | None = None,
    ) -> AIResponse:
        cfg = config or ModelConfig()
        last = messages[-1]["content"] if messages else ""
        return AIResponse(
            content=f"Echo: {last}",
            model=cfg.model,
            provider=self.name,
            usage={"prompt_tokens": 10, "completion_tokens": 5},
            finish_reason="stop",
        )
