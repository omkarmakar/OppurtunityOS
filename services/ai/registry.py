"""AI provider registry — plugin discovery and management."""

from __future__ import annotations

import logging

from core.config import get_config
from services.ai.gemini_provider import GeminiProvider
from services.ai.groq_provider import GroqProvider
from services.ai.ollama_provider import OllamaProvider
from services.ai.openai_provider import OpenAIProvider
from services.ai.openrouter_provider import OpenRouterProvider
from services.ai.provider import AIProvider

logger = logging.getLogger(__name__)


class AIRegistry:
    def __init__(self) -> None:
        self._providers: dict[str, AIProvider] = {}

    def register(self, provider: AIProvider) -> None:
        self._providers[provider.name.lower()] = provider

    def get(self, name: str) -> AIProvider:
        key = name.lower()
        if key not in self._providers:
            available = list(self._providers)
            msg = f"Unknown AI provider: {name}. Available: {available}"
            raise KeyError(msg)
        return self._providers[key]

    def list(self) -> list[str]:
        return list(self._providers)

    async def models(self) -> dict[str, list[str]]:
        result: dict[str, list[str]] = {}
        for name, p in self._providers.items():
            result[name] = await p.supported_models
        return result

    @classmethod
    def default(cls) -> AIRegistry:
        registry = cls()
        cfg = get_config()

        # Register every real provider whose key/config is present.
        # Missing keys are logged and skipped — never register a dummy/mock provider.
        provider_specs: list[tuple[str, type[AIProvider], dict[str, str]]] = [
            ("openrouter", OpenRouterProvider, {"api_key": cfg.ai.openrouter_api_key}),
            ("groq", GroqProvider, {"api_key": cfg.ai.groq_api_key}),
            ("gemini", GeminiProvider, {"api_key": cfg.ai.gemini_api_key}),
            ("openai", OpenAIProvider, {"api_key": cfg.ai.openai_api_key}),
            ("ollama", OllamaProvider, {"base_url": cfg.ai.ollama_base_url}),
        ]

        for name, provider_cls, kwargs in provider_specs:
            try:
                registry.register(provider_cls(**kwargs))
            except Exception as exc:
                logger.debug("AI provider '%s' not available: %s", name, exc)
        return registry