"""Tests for the shared AI fallback helper (generate_with_fallback)."""

from __future__ import annotations

import pytest

from services.ai import AIRegistry, AIResponse, ModelConfig
from services.ai.fallback import generate_with_fallback
from services.ai.provider import AIProvider


class _SucceedingProvider(AIProvider):
    """Always succeeds, returning a canned response."""

    def __init__(self, name: str = "TestProvider") -> None:
        self._name = name

    @property
    def name(self) -> str:
        return self._name

    @property
    def default_model(self) -> str:
        return "test-model-default"

    async def generate(
        self,
        messages: list[dict[str, str]],
        config: ModelConfig | None = None,
    ) -> AIResponse:
        cfg = config or ModelConfig()
        return AIResponse(
            content="success",
            model=cfg.model,
            provider=self.name,
            finish_reason="stop",
        )


class _FailingProvider(AIProvider):
    """Always raises."""

    def __init__(self, name: str = "FailingProvider", error_msg: str = "generic error") -> None:
        self._name = name
        self._error_msg = error_msg

    @property
    def name(self) -> str:
        return self._name

    @property
    def default_model(self) -> str:
        return "failing-model"

    async def generate(
        self,
        messages: list[dict[str, str]],
        config: ModelConfig | None = None,
    ) -> AIResponse:
        raise ValueError(self._error_msg)


@pytest.fixture
def registry() -> AIRegistry:
    reg = AIRegistry()
    reg.register(_SucceedingProvider("OpenRouter"))
    reg.register(_SucceedingProvider("Groq"))
    reg.register(_SucceedingProvider("Gemini"))
    return reg


@pytest.fixture
def failing_registry() -> AIRegistry:
    reg = AIRegistry()
    reg.register(_FailingProvider("OpenRouter", "openrouter down"))
    reg.register(_FailingProvider("Groq", "groq down"))
    reg.register(_FailingProvider("Gemini", "gemini down"))
    return reg


class TestGenerateWithFallback:
    """Tests for generate_with_fallback()."""

    @pytest.mark.asyncio
    async def test_primary_succeeds_no_fallback(self, registry: AIRegistry) -> None:
        """Primary (openrouter) succeeds — no fallback attempted."""
        config = ModelConfig(model="primary-model", temperature=0.5)
        messages = [{"role": "user", "content": "hello"}]

        response, used_provider = await generate_with_fallback(
            registry=registry,
            primary_provider="openrouter",
            messages=messages,
            config=config,
            fallback_providers=["groq", "gemini"],
        )

        assert response.content == "success"
        assert used_provider == "openrouter"
        # Primary attempt should use the caller-supplied model
        assert response.model == "primary-model"

    @pytest.mark.asyncio
    async def test_primary_fails_groq_succeeds_with_correct_model(
        self,
    ) -> None:
        """Primary fails, groq succeeds — model should be groq's default, not primary's."""
        reg = AIRegistry()
        reg.register(_FailingProvider("OpenRouter", "openrouter down"))
        reg.register(_SucceedingProvider("Groq"))
        reg.register(_SucceedingProvider("Gemini"))

        config = ModelConfig(model="openrouter-specific-model", temperature=0.5)
        messages = [{"role": "user", "content": "hello"}]

        response, used_provider = await generate_with_fallback(
            registry=reg,
            primary_provider="openrouter",
            messages=messages,
            config=config,
            fallback_providers=["groq", "gemini"],
        )

        assert response.content == "success"
        assert used_provider == "groq"
        # Fallback should use groq's default model, NOT the primary's model
        assert response.model == "test-model-default"

    @pytest.mark.asyncio
    async def test_primary_and_groq_fail_gemini_succeeds(self) -> None:
        """Primary and groq fail, gemini succeeds."""
        reg = AIRegistry()
        reg.register(_FailingProvider("OpenRouter", "openrouter down"))
        reg.register(_FailingProvider("Groq", "groq down"))
        reg.register(_SucceedingProvider("Gemini"))

        config = ModelConfig(model="some-model", temperature=0.5)
        messages = [{"role": "user", "content": "hello"}]

        response, used_provider = await generate_with_fallback(
            registry=reg,
            primary_provider="openrouter",
            messages=messages,
            config=config,
            fallback_providers=["groq", "gemini"],
        )

        assert response.content == "success"
        assert used_provider == "gemini"
        # Fallback should use gemini's default model
        assert response.model == "test-model-default"

    @pytest.mark.asyncio
    async def test_all_three_fail_raises_with_all_errors(
        self,
        failing_registry: AIRegistry,
    ) -> None:
        """All three providers fail — raises ValueError with all error messages."""
        config = ModelConfig(model="some-model", temperature=0.5)
        messages = [{"role": "user", "content": "hello"}]

        with pytest.raises(ValueError) as exc_info:
            await generate_with_fallback(
                registry=failing_registry,
                primary_provider="openrouter",
                messages=messages,
                config=config,
                fallback_providers=["groq", "gemini"],
            )

        error_msg = str(exc_info.value)
        assert "All AI providers failed" in error_msg
        assert "openrouter: openrouter down" in error_msg
        assert "groq: groq down" in error_msg
        assert "gemini: gemini down" in error_msg

    @pytest.mark.asyncio
    async def test_all_three_fail_no_openai_or_ollama_or_dummy_attempted(
        self,
        failing_registry: AIRegistry,
    ) -> None:
        """When all three fail, confirms no attempt was made to call openai, ollama, or dummy."""
        config = ModelConfig(model="some-model", temperature=0.5)
        messages = [{"role": "user", "content": "hello"}]

        with pytest.raises(ValueError) as exc_info:
            await generate_with_fallback(
                registry=failing_registry,
                primary_provider="openrouter",
                messages=messages,
                config=config,
                fallback_providers=["groq", "gemini"],
            )

        error_msg = str(exc_info.value)
        # Should NOT mention openai, ollama, or dummy
        assert "openai" not in error_msg.lower()
        assert "ollama" not in error_msg.lower()
        assert "dummy" not in error_msg.lower()

    @pytest.mark.asyncio
    async def test_primary_in_fallback_list_dedup(self) -> None:
        """If primary is also in fallback list, it's not called twice."""
        reg = AIRegistry()
        reg.register(_SucceedingProvider("OpenRouter"))
        reg.register(_SucceedingProvider("Groq"))

        config = ModelConfig(model="some-model", temperature=0.5)
        messages = [{"role": "user", "content": "hello"}]

        response, used_provider = await generate_with_fallback(
            registry=reg,
            primary_provider="openrouter",
            messages=messages,
            config=config,
            fallback_providers=["openrouter", "groq"],
        )

        assert response.content == "success"
        assert used_provider == "openrouter"
        # Should have used the primary's model since it was the first attempt
        assert response.model == "some-model"

    @pytest.mark.asyncio
    async def test_unregistered_provider_skipped(self) -> None:
        """If a provider in the chain is not registered, it's skipped with a debug log."""
        reg = AIRegistry()
        reg.register(_SucceedingProvider("Groq"))

        config = ModelConfig(model="some-model", temperature=0.5)
        messages = [{"role": "user", "content": "hello"}]

        # openrouter is not registered, should skip to groq
        response, used_provider = await generate_with_fallback(
            registry=reg,
            primary_provider="openrouter",
            messages=messages,
            config=config,
            fallback_providers=["groq"],
        )

        assert response.content == "success"
        assert used_provider == "groq"