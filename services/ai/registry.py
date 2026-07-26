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

    def models(self) -> dict[str, list[str]]:
        return {name: p.supported_models for name, p in self._providers.items()}

    @classmethod
    def default(cls) -> AIRegistry:
        registry = cls()
        cfg = get_config()
        
        # Register real providers only with fallback chain: OpenRouter → Groq
        provider_specs: list[tuple[str, type[AIProvider], dict[str, str]]] = [
            ("openrouter", OpenRouterProvider, {"api_key": cfg.ai.openrouter_api_key}),
            ("groq", GroqProvider, {"api_key": cfg.ai.groq_api_key}),
        ]

        for name, provider_cls, kwargs in provider_specs:
            try:
                registry.register(provider_cls(**kwargs))
            except Exception as exc:
                logger.debug("AI provider '%s' not available: %s", name, exc)
        return registry
