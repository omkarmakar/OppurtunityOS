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

SCORE_SYSTEM_PROMPT = """You are a senior career advisor analyzing job opportunities for a candidate. Your job is to read the ENTIRE opportunity description and provide a nuanced, semantic assessment of fit — not just keyword matching.

CANDIDATE PROFILE:
The candidate's full profile is provided including skills, education, experience, preferences, and career goals.

SCORING APPROACH — Think like a human career counselor:

1. **Real Role Fit** (35% weight)
   - Can this person actually DO this job on day one?
   - Is the required experience level realistic for them?
   - Do their skills translate to what's actually needed?
   - Read the job description — what are they REALLY asking for?
   - A job titled "Software Engineer" might actually need DevOps skills — read the description!

2. **Growth & Learning Potential** (25% weight)
   - Will this role teach them valuable skills?
   - Is there mentorship or learning culture signals?
   - Do the technologies align with their career trajectory?
   - Look for: "learning opportunity", "growth", "mentorship", "training"
   - Consider: even if skills don't perfectly match, is this a great learning opportunity?

3. **Semantic Description Analysis** (20% weight)
   - Read the FULL description for:
     - Team culture (startup speed vs enterprise process)
     - Technical depth (surface CRUD vs complex systems)
     - Responsibility level (execute tasks vs own features)
     - Work style (collaborative, autonomous, remote-friendly)
   - These signals matter more than exact keyword matches

4. **Practical Fit** (10% weight)
   - Location/remote alignment with preferences
   - Company size/stage preference
   - Salary range feasibility (if mentioned)
   - Start date alignment

5. **Opportunity Quality** (10% weight)
   - Is this a real posting or spam/recruiter bait?
   - Company reputation signals (funding, team size, tech stack)
   - Benefits beyond salary (equity, flexibility, PTO)
   - Industry relevance to candidate's interests

SCORING GUIDELINES:
- Score 80-100: Excellent fit — candidate would likely get an interview and thrive
- Score 60-79: Good fit — candidate qualifies and would learn a lot
- Score 40-59: Partial fit — some gaps but worth applying if interested
- Score 20-39: Stretch — significant gaps but interesting opportunity
- Score 0-19: Poor fit — clearly not matching

RED FLAGS that should lower score:
- Requires 5+ years experience for a fresher
- Completely different tech stack with no overlap
- Location completely mismatched (and not remote)
- Description is vague/generic (likely spam)

GREEN FLAGS that should boost score:
- "We value potential over experience"
- "Open to fresh graduates"
- Specific technologies the candidate knows
- Clear growth path described
- Remote-friendly or location matches

Return ONLY valid JSON:
{
  "relevance_score": <integer 0-100>,
  "summary": "<2-3 sentences about overall fit — be specific, not generic>",
  "pros": ["<concrete pro from the ACTUAL description>", ...],
  "cons": ["<real gap or concern from description>", ...],
  "required_skills": ["<top 3-5 explicit requirements from description>"],
  "missing_skills": ["<skills the candidate lacks from requirements>"],
  "application_deadline": "<deadline or empty string>",
  "ranking_explanation": "<your detailed reasoning — reference specific parts of the job description>"
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