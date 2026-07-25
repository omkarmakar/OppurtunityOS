"""Ollama local AI provider."""

from __future__ import annotations

import httpx

from services.ai.models import AIResponse, ModelConfig
from services.ai.provider import AIProvider

OLLAMA_BASE_URL = "http://localhost:11434"


class OllamaProvider(AIProvider):
    def __init__(self, base_url: str = OLLAMA_BASE_URL) -> None:
        self._base_url = base_url.rstrip("/")

    @property
    def name(self) -> str:
        return "Ollama"

    @property
    def supported_models(self) -> list[str]:
        return [
            "llama3.2",
            "llama3.1",
            "mistral",
            "mixtral",
            "codellama",
            "gemma2",
            "phi3",
        ]

    async def generate(
        self,
        messages: list[dict[str, str]],
        config: ModelConfig | None = None,
    ) -> AIResponse:
        cfg = config or ModelConfig()

        body = {
            "model": cfg.model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": cfg.temperature,
                "num_predict": cfg.max_tokens,
                "top_p": cfg.top_p,
            },
        }
        body.update(cfg.extra)

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self._base_url}/api/chat",
                json=body,
                timeout=300,
            )
            resp.raise_for_status()
            data = resp.json()

        return AIResponse(
            content=data["message"]["content"],
            model=data.get("model", cfg.model),
            provider=self.name,
            usage=None,
            finish_reason="stop",
        )
