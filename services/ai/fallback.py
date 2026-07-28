"""Shared fallback helper for AI provider calls.

Provides a single ``generate_with_fallback`` function used by both
query_generator.py and scorer.py, eliminating duplicated inline fallback
logic.  The fallback chain is:

    primary_provider → fallback_providers[0] → fallback_providers[1] → … → fail

No dummy/mock provider is ever injected into this chain.
"""

from __future__ import annotations

import logging
from typing import Any

from services.ai.models import AIResponse, ModelConfig
from services.ai.provider import AIProvider
from services.ai.registry import AIRegistry

logger = logging.getLogger(__name__)


async def generate_with_fallback(
    registry: AIRegistry,
    primary_provider: str,
    messages: list[dict[str, str]],
    config: ModelConfig,
    fallback_providers: list[str],
) -> tuple[AIResponse, str]:
    """Call an AI provider with automatic fallback.

    Builds the attempt order as ``[primary_provider] + fallback_providers``,
    de-duplicated while preserving order.  For each provider in that order:

    * If the provider is not registered, a debug line is logged and the next
      one is tried.
    * On the *primary* attempt the caller-supplied ``config.model`` is used.
    * On *fallback* attempts a fresh ``ModelConfig`` is built using the
      fallback provider's own ``default_model`` so that the model string is
      always valid for that provider.
    * If the provider raises, the error is collected and the next one is tried.

    Returns
    -------
    tuple[AIResponse, str]
        ``(response, provider_name)`` — the successful response and the name
        of the provider that produced it.

    Raises
    ------
    ValueError
        If every provider in the order fails.  The error message lists each
        provider tried and its specific error.
    """
    # Build de-duplicated attempt order preserving insertion order.
    seen: set[str] = set()
    attempt_order: list[str] = []
    for name in [primary_provider, *fallback_providers]:
        key = name.lower()
        if key not in seen:
            seen.add(key)
            attempt_order.append(name)

    errors: dict[str, str] = {}

    for idx, provider_name in enumerate(attempt_order):
        # Resolve provider instance from registry.
        try:
            provider: AIProvider = registry.get(provider_name)
        except KeyError:
            logger.debug(
                "Fallback provider '%s' is not registered — skipping",
                provider_name,
            )
            errors[provider_name] = "not registered"
            continue

        # Build the model config for this attempt.
        if idx == 0:
            # Primary attempt — use the caller-supplied model.
            attempt_config = config
        else:
            # Fallback attempt — use the fallback provider's own default model.
            attempt_config = ModelConfig(
                model=provider.default_model,
                temperature=config.temperature,
                max_tokens=config.max_tokens,
                top_p=config.top_p,
                extra=config.extra,
            )

        try:
            response: AIResponse = await provider.generate(messages, attempt_config)
            logger.info(
                "AI call succeeded with provider '%s' (model=%s)",
                provider_name,
                attempt_config.model,
            )
            return response, provider_name
        except Exception as exc:
            msg = str(exc)
            logger.warning(
                "AI provider '%s' failed: %s",
                provider_name,
                msg,
            )
            errors[provider_name] = msg
            continue

    # All providers failed.
    error_parts = [f"{name}: {err}" for name, err in errors.items()]
    raise ValueError(
        f"All AI providers failed — {'; '.join(error_parts)}",
    )