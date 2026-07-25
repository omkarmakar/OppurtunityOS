"""Prompt template library."""

from __future__ import annotations

from services.ai.models import PromptTemplate

DEFAULT_TEMPLATES: list[PromptTemplate] = [
    PromptTemplate(
        name="summarize",
        template="Summarize the following text concisely:\n\n{text}",
        description="Concisely summarize provided text",
        variables=["text"],
    ),
    PromptTemplate(
        name="analyze",
        template=(
            "Analyze the following content and provide key insights, "
            "main themes, and notable points:\n\n{text}"
        ),
        description="Analyze content for key insights and themes",
        variables=["text"],
    ),
    PromptTemplate(
        name="custom",
        template="{prompt}",
        description="Custom prompt with no predefined structure",
        variables=["prompt"],
    ),
]


class PromptLibrary:
    def __init__(self) -> None:
        self._templates: dict[str, PromptTemplate] = {}
        for tpl in DEFAULT_TEMPLATES:
            self.register(tpl)

    def register(self, template: PromptTemplate) -> None:
        self._templates[template.name] = template

    def get(self, name: str) -> PromptTemplate:
        if name not in self._templates:
            available = ", ".join(self._templates)
            msg = f"Unknown prompt template: {name}. Available: {available}"
            raise KeyError(msg)
        return self._templates[name]

    def list(self) -> list[PromptTemplate]:
        return list(self._templates.values())

    @classmethod
    def default(cls) -> PromptLibrary:
        return cls()
