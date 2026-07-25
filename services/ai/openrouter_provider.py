"""OpenRouter API provider (OpenAI-compatible)."""

from __future__ import annotations

import httpx

from services.ai.models import AIResponse, ModelConfig
from services.ai.provider import AIProvider

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


class OpenRouterProvider(AIProvider):
    def __init__(self, api_key: str = "", base_url: str = OPENROUTER_BASE_URL) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")

    @property
    def name(self) -> str:
        return "OpenRouter"

    @property
    def supported_models(self) -> list[str]:
        return [
            "openai/gpt-4o-mini:free",
            "openai/gpt-4o:free",
            "anthropic/claude-3.5-sonnet:free",
            "anthropic/claude-3-haiku:free",
            "google/gemini-2.0-flash:free",
            "meta-llama/llama-3.3-70b-instruct:free",
            "mistral/mistral-large:free",
            "deepseek/deepseek-chat:free",
            "nvidia/nemotron-3-ultra-550b-a55b:free",
            "google/gemma-4-26b-a4b-it:free",
            "meta-llama/llama-4-scout:free",
            "deepseek/deepseek-r1:free",
            "qwen/qwen3-235b-a22b:free",
            "qwen/qwen3-coder:free",
        ]

    async def generate(
        self,
        messages: list[dict[str, str]],
        config: ModelConfig | None = None,
    ) -> AIResponse:
        cfg = config or ModelConfig()

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        body = {
            "model": cfg.model,
            "messages": messages,
            "temperature": cfg.temperature,
            "max_tokens": cfg.max_tokens,
            "top_p": cfg.top_p,
        }
        body.update(cfg.extra)

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self._base_url}/chat/completions",
                headers=headers,
                json=body,
                timeout=120,
            )
            resp.raise_for_status()
            data = resp.json()

        choice = data["choices"][0]
        return AIResponse(
            content=choice["message"]["content"],
            model=data["model"],
            provider=self.name,
            usage=data.get("usage"),
            finish_reason=choice.get("finish_reason", ""),
        )
