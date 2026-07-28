"""AI-powered opportunity scoring against a user profile."""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from core.config import get_config
from database.models.opportunities import Opportunity
from database.models.profiles import Profile
from database.session import SessionLocal
from services.ai import AIRegistry, AIResponse, ModelConfig
from services.ai.fallback import generate_with_fallback

SCORE_SYSTEM_PROMPT = """You are an expert career opportunity analyst. Given a user's profile and job opportunity, perform deep semantic analysis to evaluate match quality.

SCORING METHODOLOGY:

1. **Skill Match Analysis** (Weight: 35%)
   - Direct skill overlap from job description vs user skills
   - Technology stack alignment
   - Domain experience relevance
   - Growth potential in required skills

2. **Role & Experience Level Match** (Weight: 30%)
   - Entry level positions for freshers/early-career
   - Junior positions for limited experience
   - Skills-based assessment vs years-of-experience requirement
   - Growth trajectory alignment

3. **Location & Work Style** (Weight: 15%)
   - Location preferences vs job location
   - Remote work availability
   - Commute feasibility
   - Work culture fit signals

4. **Compensation & Benefits** (Weight: 10%)
   - Salary expectations alignment
   - Perks and benefits value
   - Growth opportunities

5. **Opportunity Quality** (Weight: 10%)
   - Company reputation signals
   - Industry relevance
   - Learning potential
   - Long-term career value

ANALYSIS RULES:
- Read ENTIRE job description, not just title and keywords
- Evaluate cultural fit indicators (startup vs enterprise, learning focus, etc.)
- Consider hidden opportunities (mentorship, technologies to learn)
- Flag deal-breakers (over-qualification mismatch, location misalignment)
- Score for entry-level/fresher candidates appropriately
- Look for "growth opportunity" language
- Consider listed "nice-to-have" vs "must-have" skills

Return ONLY valid JSON:
{
  "relevance_score": <integer 0-100 based on overall fit>,
  "summary": "<2-3 sentences about fit>",
  "pros": ["<concrete pro from description>", ...],
  "cons": ["<potential con or gap>", ...],
  "required_skills": ["<top 3-5 explicit requirements>"],
  "missing_skills": ["<user gaps if any>"],
  "application_deadline": "<deadline or empty>",
  "ranking_explanation": "<detailed reasoning for score>"
}"""


@dataclass
class ScoredOpportunity:
    opportunity_id: str = ""
    title: str = ""
    url: str = ""
    relevance_score: float = 0.0
    summary: str = ""
    pros: list[str] = field(default_factory=list)
    cons: list[str] = field(default_factory=list)
    required_skills: list[str] = field(default_factory=list)
    missing_skills: list[str] = field(default_factory=list)
    application_deadline: str = ""
    ranking_explanation: str = ""


def _build_profile_context(profile: Profile) -> str:
    lines: list[str] = []

    if profile.display_name:
        lines.append(f"Name: {profile.display_name}")
    if profile.bio:
        lines.append(f"Bio: {profile.bio}")
    if profile.skills:
        lines.append(f"Skills: {', '.join(profile.skills)}")
    if profile.preferred_locations:
        lines.append(f"Preferred Locations: {', '.join(profile.preferred_locations)}")
    if profile.salary_expectations:
        lines.append(f"Salary Expectations: {profile.salary_expectations}")
    if profile.target_companies:
        lines.append(f"Target Companies: {', '.join(profile.target_companies)}")
    if profile.keywords:
        lines.append(f"Keywords: {', '.join(profile.keywords)}")
    if profile.experience:
        exp_summary = []
        for exp in profile.experience:
            company = exp.get("company", "")
            role = exp.get("role", "")
            if company and role:
                exp_summary.append(f"{role} at {company}")
        if exp_summary:
            lines.append(f"Experience: {'; '.join(exp_summary)}")
    if profile.education:
        edu_summary = []
        for edu in profile.education:
            deg = edu.get("degree", "")
            field_ = edu.get("field", "")
            inst = edu.get("institution", "")
            parts = [p for p in (deg, field_, inst) if p]
            if parts:
                edu_summary.append(" ".join(parts))
        if edu_summary:
            lines.append(f"Education: {'; '.join(edu_summary)}")

    return "\n".join(lines)


def _build_opportunity_context(title: str, description: str | None, url: str | None) -> str:
    lines = [f"Title: {title}"]
    if description:
        lines.append(f"Description: {description}")
    if url:
        lines.append(f"URL: {url}")
    return "\n".join(lines)


class OpportunityScorer:
    def __init__(
        self,
        provider_name: str | None = None,
        model_name: str | None = None,
    ) -> None:
        cfg = get_config()
        self._provider_name = provider_name or cfg.ai.default_provider
        self._model_name = model_name or cfg.ai.default_model
        self._registry = AIRegistry.default()
        self._fallback_providers = cfg.ai.fallback_providers

    async def score_opportunity(
        self,
        profile: Profile,
        title: str,
        description: str | None = None,
        url: str | None = None,
    ) -> ScoredOpportunity:
        profile_text = _build_profile_context(profile)
        opp_text = _build_opportunity_context(title, description, url)

        user_prompt = f"""User Profile:
{profile_text}

Opportunity:
{opp_text}

Score this opportunity against the user's profile. Return valid JSON only."""

        config = ModelConfig(model=self._model_name, temperature=0.3, max_tokens=2048)

        messages = [
            {"role": "system", "content": SCORE_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]

        response, _used_provider = await generate_with_fallback(
            registry=self._registry,
            primary_provider=self._provider_name,
            messages=messages,
            config=config,
            fallback_providers=self._fallback_providers,
        )

        result = self._parse_response(response.content)

        return ScoredOpportunity(
            opportunity_id="",
            title=title,
            url=url or "",
            relevance_score=result.get("relevance_score", 0),
            summary=result.get("summary", ""),
            pros=result.get("pros", []),
            cons=result.get("cons", []),
            required_skills=result.get("required_skills", []),
            missing_skills=result.get("missing_skills", []),
            application_deadline=result.get("application_deadline", ""),
            ranking_explanation=result.get("ranking_explanation", ""),
        )

    async def score_and_save(
        self,
        profile: Profile,
        opportunity: Opportunity,
    ) -> ScoredOpportunity:
        result = await self.score_opportunity(
            profile,
            opportunity.title,
            opportunity.description,
            opportunity.url,
        )
        result.opportunity_id = str(opportunity.id)

        opportunity.relevance_score = result.relevance_score
        opportunity.summary = result.summary
        opportunity.pros = result.pros
        opportunity.cons = result.cons
        opportunity.required_skills = result.required_skills
        opportunity.missing_skills = result.missing_skills
        opportunity.application_deadline = result.application_deadline
        opportunity.ranking_explanation = result.ranking_explanation
        opportunity.ai_scored_at = datetime.now(timezone.utc)

        return result

    async def score_multiple_and_save(
        self,
        profile: Profile,
        opportunities: list[Opportunity],
        max_concurrent: int = 5,
    ) -> list[ScoredOpportunity]:
        sem = asyncio.Semaphore(max_concurrent)

        async def _scored(opp: Opportunity) -> ScoredOpportunity:
            async with sem:
                return await self.score_and_save(profile, opp)

        tasks = [_scored(opp) for opp in opportunities]
        results = await asyncio.gather(*tasks)
        results.sort(key=lambda r: r.relevance_score, reverse=True)
        return results

    def _parse_response(self, content: str) -> dict[str, Any]:
        content = content.strip()
        if content.startswith("```"):
            content = content.split("\n", 1)[-1]
            content = content.rsplit("```", 1)[0]
        content = content.strip()
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass
        start = content.find("{")
        end = content.rfind("}")
        if start != -1 and end != -1:
            try:
                return json.loads(content[start : end + 1])
            except json.JSONDecodeError:
                pass
        return {
            "relevance_score": 0,
            "summary": content[:200],
            "pros": [],
            "cons": [],
            "required_skills": [],
            "missing_skills": [],
            "application_deadline": "",
            "ranking_explanation": "Failed to parse AI response",
        }