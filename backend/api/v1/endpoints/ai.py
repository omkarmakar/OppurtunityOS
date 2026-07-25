"""AI service endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from core.config import get_config
from services.ai import (
    AICache,
    AIRegistry,
    AIResponse,
    ModelConfig,
    PromptLibrary,
    TokenCounter,
    OpenRouterProvider,
)
from services.ai.models import PromptTemplate

router = APIRouter()
_registry = AIRegistry.default()
_library = PromptLibrary.default()
_cache = AICache(ttl=get_config().ai.cache_ttl)
_token_counter = TokenCounter()


class ChatMessage(BaseModel):
    role: str = Field(description="Message role: system, user, assistant")
    content: str = Field(description="Message content")


class GenerateRequest(BaseModel):
    messages: list[ChatMessage] = Field(description="Conversation messages")
    provider: str = Field(default="", description="Provider name (empty = default)")
    model: str = Field(default="", description="Model name (empty = default model)")
    temperature: float | None = Field(default=None, ge=0, le=2)
    max_tokens: int | None = Field(default=None, ge=1, le=128000)
    top_p: float | None = Field(default=None, ge=0, le=1)
    prompt_template: str | None = Field(default=None, description="Prompt template name")
    template_vars: dict[str, str] | None = Field(
        default=None, description="Template variables"
    )
    use_cache: bool = Field(default=True, description="Enable response caching")
    extra: dict[str, Any] = Field(default_factory=dict)


class ModelInfoResponse(BaseModel):
    id: str
    provider: str


class GenerateResponse(BaseModel):
    content: str
    model: str
    provider: str
    usage: dict[str, Any] | None = None
    cached: bool = False
    finish_reason: str = ""


class ProviderInfo(BaseModel):
    name: str
    models: list[str]


@router.post("/ai/generate", response_model=GenerateResponse)
async def generate(req: GenerateRequest) -> GenerateResponse:
    try:
        cfg = get_config()
        provider_name = req.provider or cfg.ai.default_provider
        model_name = req.model or cfg.ai.default_model

        messages = req.messages
        if req.prompt_template:
            try:
                tpl: PromptTemplate = _library.get(req.prompt_template)
                vars = req.template_vars or {}
                rendered = tpl.render(**vars)
                messages = [ChatMessage(role="user", content=rendered)]
            except KeyError as e:
                raise HTTPException(status_code=400, detail=str(e))

        model_cfg = ModelConfig(
            model=model_name,
            temperature=req.temperature or 0.7,
            max_tokens=req.max_tokens or 4096,
            top_p=req.top_p or 1.0,
            extra=req.extra,
        )
        config_dict = model_cfg.__dict__.copy()

        msg_dicts = [{"role": m.role, "content": m.content} for m in messages]

        if req.use_cache:
            cached = _cache.get(msg_dicts, config_dict)
            if cached:
                return GenerateResponse(
                    content=cached.content,
                    model=cached.model,
                    provider=cached.provider,
                    usage=cached.usage,
                    cached=True,
                    finish_reason=cached.finish_reason,
                )

        provider = _registry.get(provider_name)
        result: AIResponse = await provider.generate(msg_dicts, model_cfg)

        if req.use_cache:
            _cache.set(msg_dicts, config_dict, result)

        return GenerateResponse(
            content=result.content,
            model=result.model,
            provider=result.provider,
            usage=result.usage,
            finish_reason=result.finish_reason,
        )
    except KeyError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/ai/providers", response_model=list[ProviderInfo])
async def list_providers() -> list[ProviderInfo]:
    return [
        ProviderInfo(name=name, models=models)
        for name, models in _registry.models().items()
    ]


@router.get("/ai/templates", response_model=list[PromptTemplate])
async def list_templates() -> list[PromptTemplate]:
    return _library.list()


@router.post("/ai/count-tokens")
async def count_tokens(messages: list[ChatMessage]) -> dict:
    msg_dicts = [{"role": m.role, "content": m.content} for m in messages]
    total = _token_counter.count_message_tokens(msg_dicts)
    return {"total_tokens": total, "messages": len(msg_dicts)}
