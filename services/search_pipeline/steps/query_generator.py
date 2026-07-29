"""Pipeline step — generates search queries from user profile using AI.

Factory
-------
``create_query_generator`` reads ``cfg.ai.query_generation.backend`` and
returns either the rule-based or LLM-based generator instance so callers
do not need to know which backend is active.
"""

from __future__ import annotations

from typing import Any

import json

from core.config import get_config
from services.ai import AIRegistry, ModelConfig
from services.ai.fallback import generate_with_fallback
from services.search_pipeline.steps.base import PipelineStep
from services.search_pipeline.steps.query_generator_rules import (
    RuleBasedQueryGenerator,
)

QUERY_GENERATOR_PROMPT = """You are an expert job search assistant. Think step-by-step like a career counselor helping a candidate find the best opportunities.

CANDIDATE PROFILE:
{profile_context}

YOUR TASK: Generate exactly {count} highly targeted search queries that will return REAL, CURRENT job postings. Think about this candidate holistically — their skills, experience level, location preferences, career trajectory, and the types of companies that would value them.

THINK BEFORE YOU SEARCH:
1. What roles does this candidate qualify for RIGHT NOW? (not aspirational)
2. What companies are actively hiring for these skills?
3. What job boards and platforms are most relevant?
4. What is the best way to combine skills to find exact matches?

QUERY STRATEGY — generate a MIX from these categories:

**Direct Job Board Searches** (use site: operator for precision):
- "site:linkedin.com/jobs python developer fresher" 
- "site:naukri.com machine learning entry level"
- "site:indeed.com react developer hiring"
- "site:unstop.com software engineer internship"
- "site:wellfound.com startup developer"
- "site:glassdoor.com junior software engineer"

**Company Career Pages** (target known employers):
- "site:careers.google.com software engineer"
- "site:jobs.lever.co startup engineer"
- "site:boards.greenhouse.io developer"
- For target companies: "site:{company}.com/careers software engineer"

**Skill-Role Combinations** (precise matching):
- Combine 2-3 top skills with role title
- Example: "pytorch machine learning engineer" not just "machine learning"
- Example: "react typescript frontend developer" not just "frontend"

**Experience-Level Targeted**:
- Match to candidate's actual level (fresher/junior/mid)
- Include terms like: "0-2 years", "fresher", "junior", "entry level", "recent graduate"
- Avoid: "senior", "lead", "principal" unless profile shows that level

**Location-Aware** (if locations specified):
- "software engineer jobs {city}"
- "{city} remote developer hiring"
- Include "remote" as separate variant

RULES:
- NEVER generate generic queries like "software engineer jobs" — always include specific skills/technologies
- Each query should target a SPECIFIC type of opportunity
- Use "hiring", "apply", "opening", "vacancy" to filter out articles/tutorials
- Mix job board sites (linkedin, naukri, indeed) with direct company searches
- For freshers: emphasize "internship", "trainee", "apprentice", "fresher"
- Include at least 1 query with site: operator for a job board

Return ONLY a JSON array of strings, like: ["query 1", "query 2", ...]"""


class QueryGenerator(PipelineStep):
    def __init__(
        self,
        provider: str = "",
        model: str = "",
        query_count: int = 5,
    ) -> None:
        cfg = get_config()
        self._provider_name = provider
        self._model_name = model
        self._default_provider_name = cfg.ai.default_provider
        self._default_model_name = cfg.ai.default_model
        self._query_count = max(1, min(query_count, 20))
        self._registry = AIRegistry.default()
        self._fallback_providers = cfg.ai.fallback_providers

    @property
    def name(self) -> str:
        return "QueryGenerator"

    async def execute(self, ctx: dict[str, Any]) -> dict[str, Any]:
        profile = ctx.get("profile")
        if not profile:
            msg = "No profile found in context"
            raise ValueError(msg)

        profile_context = self._build_profile_context(profile)

        provider_name = self._provider_name or self._default_provider_name
        model_name = self._model_name or self._default_model_name

        config = ModelConfig(model=model_name, temperature=0.7, max_tokens=1024)

        prompt = QUERY_GENERATOR_PROMPT.format(
            profile_context=profile_context,
            count=self._query_count,
        )

        messages = [
            {"role": "system", "content": "You generate job search queries as JSON arrays."},
            {"role": "user", "content": prompt},
        ]

        response, used_provider = await generate_with_fallback(
            registry=self._registry,
            primary_provider=provider_name,
            messages=messages,
            config=config,
            fallback_providers=self._fallback_providers,
        )

        queries = self._parse_queries(response.content)

        if not queries:
            msg = f"AI provider returned no parseable queries. Response: {response.content[:200]}"
            raise ValueError(msg)

        ctx["queries"] = queries
        ctx["ai_provider_used"] = used_provider
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


def create_query_generator(
    provider: str = "",
    model: str = "",
    query_count: int = 5,
    enabled_plugins: list[str] | None = None,
) -> PipelineStep:
    """Factory: return a QueryGenerator or RuleBasedQueryGenerator based on config.

    Reads ``cfg.ai.query_generation.backend`` — if ``"rules"`` (the default)
    returns a ``RuleBasedQueryGenerator``; if ``"llm"`` returns the original
    ``QueryGenerator`` that calls an AI provider.
    """
    cfg = get_config()
    backend = cfg.ai.query_generation.backend
    if backend == "llm":
        return QueryGenerator(
            provider=provider,
            model=model,
            query_count=query_count,
        )
    return RuleBasedQueryGenerator(
        query_count=query_count,
        enabled_plugins=enabled_plugins,
    )