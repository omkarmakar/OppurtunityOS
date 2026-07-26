"""Groq API provider (OpenAI-compatible)."""

from __future__ import annotations

import httpx

from services.ai.models import AIResponse, ModelConfig
from services.ai.provider import AIProvider

GROQ_BASE_URL = "https://api.groq.com/openai/v1"


class GroqProvider(AIProvider):
    def __init__(self, api_key: str = "", base_url: str = GROQ_BASE_URL) -> None:
        if not api_key:
            raise ValueError("Groq API key cannot be empty")
        self._api_key = api_key.strip()
        if not self._api_key:
            raise ValueError("Groq API key is empty or contains only whitespace")
        self._base_url = base_url.rstrip("/")

    @property
    def name(self) -> str:
        return "Groq"

    @property
    def default_model(self) -> str:
        return "llama-3.3-70b-versatile"

    async def supported_models(self) -> list[str]:
        return [
            "llama-3.3-70b-versatile",
            "llama-3.1-8b-instant",
            "mixtral-8x7b-32768",
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

        # Groq does not support logprobs, logit_bias, top_logprobs per their API docs.
        # Filter these out if present in extra.
        unsupported_fields = {"logprobs", "logit_bias", "top_logprobs"}
        extra_filtered = {k: v for k, v in cfg.extra.items() if k not in unsupported_fields}
        body.update(extra_filtered)

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self._base_url}/chat/completions",
                headers=headers,
                json=body,
                timeout=120,
            )

            # Handle rate limiting with clear error messages.
            if resp.status_code == 429:
                error_data = resp.json() if resp.text else {}
                error_msg = error_data.get("error", {}).get("message", "Rate limit exceeded")
                raise ValueError(f"Groq rate limit: {error_msg}")

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
