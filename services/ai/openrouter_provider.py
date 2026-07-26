"""OpenRouter API provider (OpenAI-compatible)."""

from __future__ import annotations

import httpx
import time
import threading
from typing import ClassVar

from services.ai.models import AIResponse, ModelConfig
from services.ai.provider import AIProvider

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
# Default model changed from the non-existent "openrouter/free" to a verified real free model.
OPENROUTER_DEFAULT_MODEL = "meta-llama/llama-3.3-70b-instruct:free"


class OpenRouterProvider(AIProvider):
    # Class-level cache for free models list to avoid repeated API calls.
    _models_cache: ClassVar[dict[str, tuple[float, list[str]]]] = {}
    _models_cache_lock: ClassVar[threading.Lock] = threading.Lock()
    _models_cache_ttl: ClassVar[int] = 3600  # 1 hour TTL

    def __init__(self, api_key: str = "", base_url: str = OPENROUTER_BASE_URL) -> None:
        if not api_key:
            raise ValueError("OpenRouter API key cannot be empty")
        self._api_key = api_key.strip()
        if not self._api_key:
            raise ValueError("OpenRouter API key is empty or contains only whitespace")
        self._base_url = base_url.rstrip("/")

    @property
    def name(self) -> str:
        return "OpenRouter"

    async def _fetch_free_models(self) -> list[str]:
        """Fetch live list of free models from OpenRouter's API endpoint.
        
        Returns only model IDs ending in ':free'. Caches result for 1 hour
        to avoid repeated API calls. On network error, falls back to a
        minimal verified list.
        """
        cache_key = "openrouter_free_models"
        now = time.time()
        
        # Check if cached result is still valid
        with self._models_cache_lock:
            if cache_key in self._models_cache:
                timestamp, models = self._models_cache[cache_key]
                if now - timestamp < self._models_cache_ttl:
                    return models
        
        # Fetch fresh list from API
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    f"{self._base_url}/models",
                    headers={"Authorization": f"Bearer {self._api_key}"},
                    timeout=10,
                )
                resp.raise_for_status()
                data = resp.json()
            
            # Extract model IDs ending in ':free'
            if isinstance(data, dict) and "data" in data:
                models = [
                    m["id"] for m in data["data"]
                    if isinstance(m, dict) and m.get("id", "").endswith(":free")
                ]
            else:
                # Unexpected response format; use fallback
                models = self._get_fallback_models()
        except Exception:
            # Network error or API issue; use fallback
            models = self._get_fallback_models()
        
        # Cache the result
        with self._models_cache_lock:
            self._models_cache[cache_key] = (now, models)
        
        return models

    @staticmethod
    def _get_fallback_models() -> list[str]:
        """Fallback list of verified free models on OpenRouter.
        
        Only includes models confirmed to be real and available as free-tier
        on OpenRouter as of July 2026. Updated manually as the platform evolves.
        """
        return [
            "meta-llama/llama-3.3-70b-instruct:free",
            "deepseek/deepseek-chat:free",
            "deepseek/deepseek-r1:free",
        ]

    @property
    def supported_models(self) -> list[str]:
        """Returns the fallback list of supported free models.
        
        Note: For async fetching of live models, use _fetch_free_models().
        This property is sync-only for compatibility with the AIProvider interface.
        """
        return self._get_fallback_models()

    def _resolve_model(self, config: ModelConfig) -> str:
        model = (config.model or "").strip() or OPENROUTER_DEFAULT_MODEL
        if model.endswith(":free"):
            return model
        msg = (
            "OpenRouter is restricted to free models only. "
            f"Use '{OPENROUTER_DEFAULT_MODEL}' or any model ending with ':free', got '{model}'."
        )
        raise ValueError(msg)

    async def generate(
        self,
        messages: list[dict[str, str]],
        config: ModelConfig | None = None,
    ) -> AIResponse:
        cfg = config or ModelConfig()
        model = self._resolve_model(cfg)

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        body = {
            "model": model,
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
