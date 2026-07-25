"""AI service data models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class AIMessage:
    role: str = ""
    content: str = ""


@dataclass
class ModelConfig:
    model: str = "gpt-4o-mini"
    temperature: float = 0.7
    max_tokens: int = 4096
    top_p: float = 1.0
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class AIResponse:
    content: str = ""
    model: str = ""
    provider: str = ""
    usage: dict[str, Any] | None = None
    cached: bool = False
    finish_reason: str = ""


@dataclass
class PromptTemplate:
    name: str = ""
    template: str = ""
    description: str = ""
    variables: list[str] = field(default_factory=list)

    def render(self, **kwargs: str) -> str:
        return self.template.format(**kwargs)


@dataclass
class ModelInfo:
    id: str
    provider: str
    display_name: str = ""
    context_length: int = 4096
    supports_streaming: bool = True
    supports_vision: bool = False
