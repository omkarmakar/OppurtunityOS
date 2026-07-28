"""Auto-detect and cache free LLM models from OpenRouter."""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)


class OpenRouterFreeModelResolver:
    """Resolves available free models from OpenRouter with 1-hour caching."""

    # Preferred free model order: kimi, glm, deepseek, qwen, nemotron, minimax
    PREFERRED_FREE_MODELS = [
        "kimi",
        "glm",
        "deepseek",
        "qwen",
        "nemotron",
        "minimax",
    ]

    OPENROUTER_API_URL = "https://openrouter.ai/api/v1"
    CACHE_TTL_SECONDS = 3600  # 1 hour

    def __init__(self, api_key: str | None = None) -> None:
        """Initialize resolver with optional API key.

        Args:
            api_key: OpenRouter API key (optional, may be in environment)
        """
        self._api_key = api_key
        self._cache: dict[str, Any] = {}
        self._cache_time = 0

    async def resolve_free_model(self, pinned_model: str | None = None) -> Optional[str]:
        """Resolve a free model ID, respecting pinned choice.

        Args:
            pinned_model: User-pinned model ID (overrides auto-resolution)

        Returns:
            Model ID string or None if no free model found
        """
        if pinned_model:
            logger.info(f"Using pinned model: {pinned_model}")
            return pinned_model

        try:
            models = await self._get_free_models()
            if not models:
                logger.warning("No free models found from OpenRouter")
                return None

            # Return first available in preferred order
            selected = models[0]
            logger.info(f"Auto-resolved free model: {selected['id']}")
            return selected["id"]

        except Exception as e:
            logger.error(f"Error resolving free model: {e}")
            return None

    async def _get_free_models(self) -> list[dict[str, str]]:
        """Fetch and cache available free models from OpenRouter.

        Returns:
            List of free model dictionaries with 'id' and 'name' keys
        """
        now = time.time()
        if self._cache and (now - self._cache_time < self.CACHE_TTL_SECONDS):
            logger.debug("Using cached free models")
            return self._cache.get("free_models", [])

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    f"{self.OPENROUTER_API_URL}/models",
                    timeout=10,
                )
                resp.raise_for_status()
                data = resp.json()

            models_data = data.get("data", [])
            free_models = self._filter_free_models(models_data)

            # Cache the results
            self._cache["free_models"] = free_models
            self._cache_time = now

            logger.info(f"Resolved {len(free_models)} free models from OpenRouter")
            return free_models

        except Exception as e:
            logger.error(f"Error fetching models from OpenRouter: {e}")
            # Return cached if available even if stale
            return self._cache.get("free_models", [])

    def _filter_free_models(self, models: list[dict[str, Any]]) -> list[dict[str, str]]:
        """Filter to free models and sort by preference.

        Args:
            models: Raw models list from OpenRouter API

        Returns:
            Sorted list of free model dictionaries
        """
        free_models = []

        for model in models:
            model_id: str = model.get("id", "")
            if not model_id:
                continue

            # Check if free (pricing exists and free tier available)
            pricing = model.get("pricing", {})
            prompt_price = float(pricing.get("prompt", "0")) if pricing.get("prompt") else 0
            completion_price = float(pricing.get("completion", "0")) if pricing.get("completion") else 0

            is_free = prompt_price == 0 and completion_price == 0

            if is_free:
                free_models.append({
                    "id": model_id,
                    "name": model.get("name", model_id),
                    "context_length": model.get("context_length", 0),
                })

        # Sort by preferred order
        def preference_sort(model: dict[str, str]) -> tuple[int, str]:
            model_id = model["id"].lower()
            for i, prefix in enumerate(self.PREFERRED_FREE_MODELS):
                if prefix in model_id:
                    return (i, model_id)
            return (len(self.PREFERRED_FREE_MODELS), model_id)

        free_models.sort(key=preference_sort)
        return free_models

    def invalidate_cache(self) -> None:
        """Force cache invalidation to fetch fresh models next time."""
        self._cache.clear()
        self._cache_time = 0
        logger.info("Free models cache invalidated")

    def get_cache_age_seconds(self) -> float:
        """Get age of cached models in seconds.

        Returns:
            Seconds since last fetch, or -1 if no cache
        """
        if not self._cache:
            return -1
        return time.time() - self._cache_time
