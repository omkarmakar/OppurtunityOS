"""Pipeline step — generates search queries from user profile using AI."""

from __future__ import annotations

from typing import Any

import json

from services.ai import AIRegistry, ModelConfig
from services.ai.models import AIResponse
from services.search_pipeline.steps.base import PipelineStep

QUERY_GENERATOR_PROMPT = """You are an expert job search query generator. Analyze the user's profile and create highly specific, targeted search queries that will return relevant job opportunities.

User Profile:
{profile_context}

Instructions:
1. Generate {count} distinct search queries
2. Each query should target different aspects: specific skills combinations, role variations, industry-specific terms, location-based searches
3. Use natural language that job boards and search engines understand
4. Include relevant keywords from the profile (skills, technologies, tools)
5. Mix broad queries with specific niche queries
6. Consider experience level implied by the profile
7. If locations are specified, include location-specific queries
8. Format queries as if typing into a job search engine (e.g., "senior python engineer remote", "full stack developer react nodejs")

Return ONLY a JSON array of strings, like: ["query 1", "query 2", ...]"""


class QueryGenerator(PipelineStep):
    def __init__(
        self,
        provider: str = "",
        model: str = "",
        query_count: int = 5,
    ) -> None:
        self._provider_name = provider
        self._model_name = model
        self._query_count = max(1, min(query_count, 20))
        self._registry = AIRegistry.default()

    @property
    def name(self) -> str:
        return "QueryGenerator"

    async def execute(self, ctx: dict[str, Any]) -> dict[str, Any]:
        profile = ctx.get("profile")
        if not profile:
            msg = "No profile found in context"
            raise ValueError(msg)

        profile_context = self._build_profile_context(profile)

        provider_name = self._provider_name or "dummyai"
        model_name = self._model_name or "dummy-model"
        
        try:
            provider = self._registry.get(provider_name)
        except Exception as e:
            msg = f"Failed to get AI provider '{provider_name}': {e}"
            raise ValueError(msg) from e

        config = ModelConfig(model=model_name, temperature=0.7, max_tokens=1024)

        prompt = QUERY_GENERATOR_PROMPT.format(
            profile_context=profile_context,
            count=self._query_count,
        )

        messages = [
            {"role": "system", "content": "You generate job search queries as JSON arrays."},
            {"role": "user", "content": prompt},
        ]

        try:
            response: AIResponse = await provider.generate(messages, config)
        except Exception as e:
            msg = f"AI provider '{provider_name}' failed to generate response: {e}"
            raise ValueError(msg) from e

        queries = self._parse_queries(response.content)
        
        if not queries:
            msg = f"AI provider returned no parseable queries. Response: {response.content[:200]}"
            raise ValueError(msg)

        ctx["queries"] = queries
        return ctx

    def _build_profile_context(self, profile: Any) -> str:
        lines: list[str] = []
        if profile.display_name:
            lines.append(f"Name: {profile.display_name}")
        if profile.bio:
            lines.append(f"Bio: {profile.bio}")
        if profile.skills:
            lines.append(f"Skills: {', '.join(profile.skills)}")
        if profile.preferred_locations:
            lines.append(f"Locations: {', '.join(profile.preferred_locations)}")
        if profile.target_companies:
            lines.append(f"Target Companies: {', '.join(profile.target_companies)}")
        if profile.keywords:
            lines.append(f"Keywords: {', '.join(profile.keywords)}")
        if profile.experience:
            roles = [e.get("role", "") for e in profile.experience if e.get("role")]
            if roles:
                lines.append(f"Past Roles: {', '.join(roles)}")
        if profile.education:
            fields = [e.get("field", "") for e in profile.education if e.get("field")]
            if fields:
                lines.append(f"Education Fields: {', '.join(fields)}")
        return "\n".join(lines) if lines else "No profile details available."

    def _parse_queries(self, content: str) -> list[str]:
        content = content.strip()
        if content.startswith("```"):
            content = content.split("\n", 1)[-1]
            content = content.rsplit("```", 1)[0]
        content = content.strip()
        try:
            parsed = json.loads(content)
            if isinstance(parsed, list):
                return [str(q) for q in parsed if q]
        except json.JSONDecodeError:
            pass
        lines = [l.strip("- ").strip() for l in content.split("\n") if l.strip()]
        return [l for l in lines if len(l) > 5][:self._query_count]
