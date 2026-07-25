"""AI service tests."""

from __future__ import annotations

import pytest

from services.ai import (
    AICache,
    AIRegistry,
    AIResponse,
    DummyAIProvider,
    GeminiProvider,
    ModelConfig,
    OllamaProvider,
    OpenAIProvider,
    OpenRouterProvider,
    PromptLibrary,
    TokenCounter,
    retry_with_backoff,
    retryable,
)
from services.ai.models import AIMessage, PromptTemplate


class TestAIMessage:
    def test_default_fields(self) -> None:
        msg = AIMessage()
        assert msg.role == ""
        assert msg.content == ""

    def test_all_fields(self) -> None:
        msg = AIMessage(role="user", content="hello")
        assert msg.role == "user"
        assert msg.content == "hello"


class TestModelConfig:
    def test_defaults(self) -> None:
        cfg = ModelConfig()
        assert cfg.model == "gpt-4o-mini"
        assert cfg.temperature == 0.7
        assert cfg.max_tokens == 4096
        assert cfg.top_p == 1.0

    def test_custom_values(self) -> None:
        cfg = ModelConfig(model="gemini-2.0-flash", temperature=0.0, max_tokens=1024)
        assert cfg.model == "gemini-2.0-flash"
        assert cfg.temperature == 0.0
        assert cfg.max_tokens == 1024


class TestAIResponse:
    def test_default_fields(self) -> None:
        r = AIResponse()
        assert r.content == ""
        assert r.model == ""
        assert r.provider == ""
        assert r.usage is None
        assert r.cached is False
        assert r.finish_reason == ""

    def test_all_fields(self) -> None:
        r = AIResponse(
            content="Hello!",
            model="gpt-4o-mini",
            provider="OpenAI",
            usage={"prompt_tokens": 10, "completion_tokens": 5},
            cached=True,
            finish_reason="stop",
        )
        assert r.content == "Hello!"
        assert r.usage == {"prompt_tokens": 10, "completion_tokens": 5}
        assert r.cached is True


class TestPromptTemplate:
    def test_defaults(self) -> None:
        t = PromptTemplate()
        assert t.name == ""
        assert t.template == ""
        assert t.variables == []

    def test_render(self) -> None:
        t = PromptTemplate(name="greet", template="Hello {name}!", variables=["name"])
        assert t.render(name="World") == "Hello World!"

    def test_render_custom_template(self) -> None:
        t = PromptTemplate(
            name="analyze",
            template="Analyze: {text}",
            variables=["text"],
        )
        assert t.render(text="foo bar") == "Analyze: foo bar"


class TestDummyAIProvider:
    @pytest.mark.asyncio
    async def test_name(self) -> None:
        p = DummyAIProvider()
        assert p.name == "DummyAI"

    @pytest.mark.asyncio
    async def test_supported_models(self) -> None:
        p = DummyAIProvider()
        assert "dummy-model" in p.supported_models

    @pytest.mark.asyncio
    async def test_generate_returns_echo(self) -> None:
        p = DummyAIProvider()
        result = await p.generate([{"role": "user", "content": "hello world"}])
        assert "hello world" in result.content
        assert result.provider == "DummyAI"
        assert result.model == "gpt-4o-mini"

    @pytest.mark.asyncio
    async def test_generate_with_custom_config(self) -> None:
        p = DummyAIProvider()
        cfg = ModelConfig(model="custom-model")
        result = await p.generate(
            [{"role": "user", "content": "test"}], config=cfg
        )
        assert result.model == "custom-model"

    @pytest.mark.asyncio
    async def test_generate_usage(self) -> None:
        p = DummyAIProvider()
        result = await p.generate([{"role": "user", "content": "hi"}])
        assert result.usage is not None
        assert result.usage["prompt_tokens"] == 10
        assert result.usage["completion_tokens"] == 5

    @pytest.mark.asyncio
    async def test_generate_empty_messages(self) -> None:
        p = DummyAIProvider()
        result = await p.generate([])
        assert result.content == "Echo: "


class TestOpenAIProvider:
    def test_name(self) -> None:
        p = OpenAIProvider()
        assert p.name == "OpenAI"

    def test_supported_models(self) -> None:
        p = OpenAIProvider()
        assert "gpt-4o-mini" in p.supported_models

    @pytest.mark.asyncio
    async def test_raises_without_api_key(self) -> None:
        p = OpenAIProvider(api_key="")
        with pytest.raises(Exception):
            await p.generate([{"role": "user", "content": "hi"}])


class TestGeminiProvider:
    def test_name(self) -> None:
        p = GeminiProvider()
        assert p.name == "Gemini"

    def test_supported_models(self) -> None:
        p = GeminiProvider()
        assert "gemini-2.0-flash" in p.supported_models

    @pytest.mark.asyncio
    async def test_raises_without_api_key(self) -> None:
        p = GeminiProvider(api_key="")
        with pytest.raises(Exception):
            await p.generate([{"role": "user", "content": "hi"}])


class TestOpenRouterProvider:
    def test_name(self) -> None:
        p = OpenRouterProvider(api_key="sk-or-test")
        assert p.name == "OpenRouter"

    def test_supported_models(self) -> None:
        p = OpenRouterProvider(api_key="sk-or-test")
        assert "openrouter/free" in p.supported_models

    def test_rejects_non_free_model(self) -> None:
        p = OpenRouterProvider(api_key="sk-or-test")
        with pytest.raises(ValueError, match="restricted to free models only"):
            p._resolve_model(ModelConfig(model="openai/gpt-4o"))

    def test_accepts_free_router_when_model_missing(self) -> None:
        p = OpenRouterProvider(api_key="sk-or-test")
        assert p._resolve_model(ModelConfig(model="")) == "openrouter/free"

    @pytest.mark.asyncio
    async def test_raises_without_api_key(self) -> None:
        with pytest.raises(ValueError):
            OpenRouterProvider(api_key="")


class TestOllamaProvider:
    def test_name(self) -> None:
        p = OllamaProvider()
        assert p.name == "Ollama"

    def test_supported_models(self) -> None:
        p = OllamaProvider()
        assert "llama3.2" in p.supported_models

    @pytest.mark.asyncio
    async def test_raises_when_offline(self) -> None:
        p = OllamaProvider(base_url="http://localhost:1")
        with pytest.raises(Exception):
            await p.generate([{"role": "user", "content": "hi"}])


class TestAIRegistry:
    def test_default_registry_contains_builtins(self) -> None:
        reg = AIRegistry.default()
        providers = reg.list()
        assert "dummyai" in providers

    def test_get_known_provider(self) -> None:
        reg = AIRegistry.default()
        p = reg.get("dummyai")
        assert isinstance(p, DummyAIProvider)

    def test_get_unknown_provider_raises(self) -> None:
        reg = AIRegistry.default()
        with pytest.raises(KeyError):
            reg.get("nonexistent")

    def test_register_custom_provider(self) -> None:
        reg = AIRegistry()

        class CustomProvider(DummyAIProvider):
            @property
            def name(self) -> str:
                return "Custom"

        reg.register(CustomProvider())
        assert "custom" in reg.list()
        assert isinstance(reg.get("custom"), CustomProvider)

    def test_models_returns_dict(self) -> None:
        reg = AIRegistry.default()
        models = reg.models()
        assert isinstance(models, dict)
        assert "dummyai" in models


class TestPromptLibrary:
    def test_default_contains_builtins(self) -> None:
        lib = PromptLibrary.default()
        templates = lib.list()
        names = [t.name for t in templates]
        assert "summarize" in names
        assert "analyze" in names
        assert "custom" in names

    def test_get_known_template(self) -> None:
        lib = PromptLibrary.default()
        t = lib.get("summarize")
        assert t.name == "summarize"
        assert "{text}" in t.template

    def test_get_unknown_template_raises(self) -> None:
        lib = PromptLibrary.default()
        with pytest.raises(KeyError):
            lib.get("nonexistent")

    def test_register_custom(self) -> None:
        lib = PromptLibrary()
        t = PromptTemplate(name="custom_greet", template="Hi {name}!", variables=["name"])
        lib.register(t)
        assert "custom_greet" in [t.name for t in lib.list()]

    def test_render_template(self) -> None:
        lib = PromptLibrary.default()
        result = lib.get("summarize").render(text="Hello world")
        assert "Hello world" in result


class TestAICache:
    def test_set_and_get(self) -> None:
        cache = AICache(ttl=300)
        response = AIResponse(content="test", model="m", provider="p")
        cache.set(
            [{"role": "user", "content": "hi"}],
            {"model": "m", "temperature": 0.7},
            response,
        )
        cached = cache.get(
            [{"role": "user", "content": "hi"}],
            {"model": "m", "temperature": 0.7},
        )
        assert cached is not None
        assert cached.content == "test"

    def test_cache_miss(self) -> None:
        cache = AICache(ttl=300)
        result = cache.get(
            [{"role": "user", "content": "hi"}],
            {"model": "m"},
        )
        assert result is None

    def test_cache_clear(self) -> None:
        cache = AICache(ttl=300)
        response = AIResponse(content="test", model="m", provider="p")
        cache.set(
            [{"role": "user", "content": "hi"}],
            {"model": "m"},
            response,
        )
        cache.clear()
        assert cache.size == 0

    def test_cache_ttl_expiry(self) -> None:
        cache = AICache(ttl=0)
        response = AIResponse(content="test", model="m", provider="p")
        cache.set(
            [{"role": "user", "content": "hi"}],
            {"model": "m"},
            response,
        )
        cached = cache.get(
            [{"role": "user", "content": "hi"}],
            {"model": "m"},
        )
        assert cached is None

    def test_cache_different_keys(self) -> None:
        cache = AICache(ttl=300)
        response = AIResponse(content="test", model="m", provider="p")
        cache.set(
            [{"role": "user", "content": "hi"}],
            {"model": "m"},
            response,
        )
        result = cache.get(
            [{"role": "user", "content": "bye"}],
            {"model": "m"},
        )
        assert result is None


class TestTokenCounter:
    def test_singleton(self) -> None:
        c1 = TokenCounter()
        c2 = TokenCounter()
        assert c1 is c2

    def test_count_tokens(self) -> None:
        counter = TokenCounter()
        count = counter.count_tokens("hello world")
        assert count == len("hello world") // 4

    def test_count_message_tokens(self) -> None:
        counter = TokenCounter()
        messages = [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "world"},
        ]
        total = counter.count_message_tokens(messages)
        assert total > 0
        assert total == (len("hello") + len("world") + len("user") + len("assistant")) // 4


class TestRetryLogic:
    @pytest.mark.asyncio
    async def test_retry_success_after_failure(self) -> None:
        call_count = 0

        async def flaky() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise TimeoutError("timeout")
            return "success"

        result = await retry_with_backoff(
            flaky, _max_retries=3, _base_delay=0.01
        )
        assert result == "success"
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_retry_all_fail(self) -> None:
        call_count = 0

        async def always_fails() -> str:
            nonlocal call_count
            call_count += 1
            raise TimeoutError("fail")

        with pytest.raises(RuntimeError, match="retry attempts failed"):
            await retry_with_backoff(
                always_fails, _max_retries=2, _base_delay=0.01
            )
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_retry_non_retryable_exception(self) -> None:
        async def raises_value_error() -> str:
            raise ValueError("not retryable")

        with pytest.raises(ValueError, match="not retryable"):
            await retry_with_backoff(
                raises_value_error, _max_retries=2, _base_delay=0.01
            )

    @pytest.mark.asyncio
    async def test_retryable_decorator(self) -> None:
        call_count = 0

        @retryable(max_retries=2, base_delay=0.01)
        async def flaky() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise TimeoutError("timeout")
            return "ok"

        result = await flaky()
        assert result == "ok"
        assert call_count == 2
