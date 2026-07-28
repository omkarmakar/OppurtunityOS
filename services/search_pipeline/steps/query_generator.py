"""Pipeline step — generates search queries from user profile using AI."""

from __future__ import annotations

from typing import Any

import json

from core.config import get_config
from services.ai import AIRegistry, ModelConfig
from services.ai.models import AIResponse
from services.search_pipeline.steps.base import PipelineStep

QUERY_GENERATOR_PROMPT = """You are an expert job search query generator specializing in finding REAL opportunities on major job boards and company websites.

User Profile:
{profile_context}

TASK: Generate {count} diverse, high-quality search queries that will return ACTUAL JOB POSTINGS from:
- LinkedIn jobs
- Naukri.com
- Indeed
- Unstop
- Company career pages
- AngelList

QUERY GENERATION STRATEGY:

1. **Skill-Based Queries**: Combine primary skills with job keywords
   Example: "python django backend developer jobs"
   
2. **Role + Experience Level**: Target entry-level/fresher positions
   Example: "junior frontend developer hiring 0-1 years experience"
   
3. **Location-Specific**: Include geography where specified
   Example: "software developer jobs Bangalore remote India"
   
4. **Technology Stack Queries**: Search for specific technology combinations
   Example: "React JavaScript web developer positions"
   
5. **Company/Industry Focus**: Target specific sectors if mentioned
   Example: "fintech software engineer jobs hiring"
   
6. **Remote/Flexible Work**: Include modern work preferences
   Example: "work from home developer jobs India"
   
7. **Application-Focused**: Search for active hiring
   Example: "hiring now software engineer fresher jobs"
   
8. **Competitive Terms**: Combine skills with hiring keywords
   Example: "looking for python developer job opening"

CRITICAL RULES:
- AVOID: tutorials, courses, roadmaps, learning guides, how-to articles, certification prep
- INCLUDE: "job", "hiring", "position", "vacancy", "opening", "recruitment", "apply", "career"
- Each query MUST be realistic - as if searching on job boards
- Mix exact skill names with general terms
- Include location variants (city, region, country, "remote")
- For freshers/students: emphasize "entry level", "fresher", "junior", "graduate", "trainee", "internship"

Return ONLY valid JSON array of strings: ["query 1", "query 2", ...]"""


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
        provider = None
        original_provider_name = provider_name

        # Try to get the requested provider first
        try:
            provider = self._registry.get(provider_name)
        except Exception as e:
            pass

        # If that fails, try fallback providers in order: groq, then openrouter
        if not provider:
            fallback_order = ["groq", "openrouter"]
            for fallback_name in fallback_order:
                try:
                    provider = self._registry.get(fallback_name)
                    provider_name = fallback_name
                    break
                except Exception:
                    pass

        if not provider:
            msg = f"No AI provider available. Requested: {original_provider_name}, Available: {self._registry.list()}"
            raise ValueError(msg)

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
            # If primary provider fails, try groq as fallback
            if provider_name != "groq":
                try:
                    provider = self._registry.get("groq")
                    provider_name = "groq"
                    config = ModelConfig(model=model_name, temperature=0.7, max_tokens=1024)
                    response: AIResponse = await provider.generate(messages, config)
                except Exception as groq_error:
                    msg = f"AI provider '{original_provider_name}' failed with: {e}. Fallback Groq also failed: {groq_error}"
                    raise ValueError(msg) from e
            else:
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
