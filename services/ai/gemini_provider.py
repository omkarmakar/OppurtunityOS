"""Google Gemini API provider."""

from __future__ import annotations

from typing import Any

import httpx

from services.ai.models import AIResponse, ModelConfig
from services.ai.provider import AIProvider

GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1"


class GeminiProvider(AIProvider):
    def __init__(self, api_key: str = "") -> None:
        self._api_key = api_key

    @property
    def name(self) -> str:
        return "Gemini"

    @property
    def default_model(self) -> str:
        return "gemini-2.0-flash"

    async def supported_models(self) -> list[str]:
        return [
            "gemini-2.0-flash",
            "gemini-2.0-flash-lite",
            "gemini-1.5-pro",
            "gemini-1.5-flash",
        ]

    async def generate(
        self,
        messages: list[dict[str, str]],
        config: ModelConfig | None = None,
    ) -> AIResponse:
        cfg = config or ModelConfig()

        system_instruction, gemini_contents = self._convert_messages(messages)

        body: dict[str, Any] = {
            "contents": gemini_contents,
            "generationConfig": {
                "temperature": cfg.temperature,
                "maxOutputTokens": cfg.max_tokens,
                "topP": cfg.top_p,
            },
        }
        if system_instruction:
            body["system_instruction"] = {
                "parts": [{"text": system_instruction}]
            }

        url = f"{GEMINI_BASE_URL}/models/{cfg.model}:generateContent"

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                url,
                json=body,
                timeout=120,
                headers={"x-goog-api-key": self._api_key},
            )
            if not resp.is_success:
                error_body = resp.json() if resp.text else {}
                error_msg = (
                    error_body.get("error", {}).get("message", "")
                    or error_body.get("error", {}).get("status", "")
                    or resp.text[:200]
                )
                raise ValueError(f"Gemini API error ({resp.status_code}): {error_msg}")
            data = resp.json()

        candidate = data["candidates"][0]
        content_parts = candidate["content"]["parts"]
        text = "".join(p.get("text", "") for p in content_parts)

        usage = data.get("usageMetadata")

        return AIResponse(
            content=text,
            model=cfg.model,
            provider=self.name,
            usage=usage,
            finish_reason=candidate.get("finishReason", ""),
        )

    def _convert_messages(
        self, messages: list[dict[str, str]]
    ) -> tuple[str | None, list[dict]]:
        system_parts: list[str] = []
        contents: list[dict] = []
        for msg in messages:
            role = msg["role"]
            if role == "system":
                system_parts.append(msg["content"])
            else:
                gemini_role = "model" if role == "assistant" else "user"
                contents.append({
                    "role": gemini_role,
                    "parts": [{"text": msg["content"]}],
                })
        system_instruction = "\n".join(system_parts) if system_parts else None
        return system_instruction, contents
