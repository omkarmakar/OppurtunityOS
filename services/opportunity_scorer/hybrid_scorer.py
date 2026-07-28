"""Hybrid scoring system combining embeddings + LLM re-ranking.

Approach:
1. Embedding-based filtering: Fast semantic search using embeddings
2. Borderline re-ranking: Use Gemini to evaluate ~10% of borderline cases
3. Deterministic scoring: Score all based on skill gaps, recency, company signals
"""

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID

from database.models.opportunities import Opportunity
from database.models.profiles import Profile
from services.ai import AIRegistry, ModelConfig
from services.search_pipeline.dedup import token_set_similarity, normalize_text

logger = logging.getLogger(__name__)


@dataclass
class HybridScoreResult:
    """Scoring result with decision path."""

    opportunity_id: Optional[str]
    title: str
    company: Optional[str]
    relevance_score: int  # 0-100
    decision_path: str  # "embedding_filter" | "gemini_rerank" | "deterministic"
    reasoning: str
    pros: list[str]
    cons: list[str]
    required_skills: list[str]
    missing_skills: list[str]


class HybridOpportunityScorer:
    """Hybrid scorer: embedding filtering + Gemini re-ranking + deterministic scoring."""

    def __init__(self, ai_registry: Optional[AIRegistry] = None):
        self._registry = ai_registry or AIRegistry.default()

    async def score(
        self,
        profile: Profile,
        opportunity: Opportunity,
    ) -> HybridScoreResult:
        """Score an opportunity using hybrid approach.

        Args:
            profile: User profile with skills
            opportunity: Opportunity to score

        Returns:
            HybridScoreResult with score and decision path
        """
        # Fast path: embedding-based filtering
        embedding_score = self._embedding_filter(profile, opportunity)
        
        if embedding_score < 25:
            # Reject: poor semantic match
            return HybridScoreResult(
                opportunity_id=str(opportunity.id) if opportunity.id else None,
                title=opportunity.title or "N/A",
                company=opportunity.company or "N/A",
                relevance_score=embedding_score,
                decision_path="embedding_filter",
                reasoning="Low semantic match to profile",
                pros=[],
                cons=["Poor fit with skills and experience"],
                required_skills=[],
                missing_skills=list(profile.skills or []),
            )
        
        if embedding_score > 75:
            # Accept: strong semantic match
            return HybridScoreResult(
                opportunity_id=str(opportunity.id) if opportunity.id else None,
                title=opportunity.title or "N/A",
                company=opportunity.company or "N/A",
                relevance_score=embedding_score,
                decision_path="embedding_filter",
                reasoning="Strong semantic match to profile",
                pros=["Skills align well", "Good experience fit"],
                cons=[],
                required_skills=self._extract_skills(opportunity.description or ""),
                missing_skills=[],
            )
        
        # Borderline: use Gemini for nuanced evaluation
        return await self._gemini_rerank(profile, opportunity, embedding_score)

    def _embedding_filter(self, profile: Profile, opportunity: Opportunity) -> int:
        """Fast embedding-based filtering using text overlap.

        Args:
            profile: User profile
            opportunity: Opportunity to score

        Returns:
            Score 0-100 based on semantic similarity
        """
        profile_text = " ".join(
            list(profile.skills or [])
            + list(profile.keywords or [])
            + [profile.display_name or ""]
        ).lower()
        
        opp_text = (
            f"{opportunity.title} {opportunity.company} {opportunity.description or ''}"
        ).lower()
        
        # Token-based similarity
        profile_tokens = set(normalize_text(profile_text).split())
        opp_tokens = set(normalize_text(opp_text).split())
        
        if not profile_tokens or not opp_tokens:
            return 50
        
        overlap = len(profile_tokens & opp_tokens)
        union = len(profile_tokens | opp_tokens)
        
        jaccard_score = (overlap / union) * 100 if union > 0 else 0
        
        # Boost score if company is relevant or location matches
        boost = 0
        if opportunity.company and any(
            kw.lower() in opportunity.company.lower()
            for kw in (profile.keywords or [])
        ):
            boost += 10
        
        return min(100, int(jaccard_score + boost))

    async def _gemini_rerank(
        self,
        profile: Profile,
        opportunity: Opportunity,
        embedding_score: int,
    ) -> HybridScoreResult:
        """Use Gemini to re-rank borderline opportunities.

        Args:
            profile: User profile
            opportunity: Opportunity to score
            embedding_score: Initial embedding-based score (25-75)

        Returns:
            HybridScoreResult with Gemini reasoning
        """
        try:
            provider = self._registry.get("openrouter")
        except Exception:
            try:
                provider = self._registry.get("groq")
            except Exception:
                # Fallback to deterministic if no LLM
                return self._deterministic_score(profile, opportunity, embedding_score)
        
        profile_context = self._format_profile_context(profile)
        opp_context = self._format_opportunity_context(opportunity)
        
        prompt = f"""You are a career advisor evaluating job fit. Be decisive but nuanced.

User Profile:
{profile_context}

Job Opportunity:
{opp_context}

Evaluate this opportunity (which initially scored {embedding_score}/100 on semantic match).
Consider: skill alignment, growth opportunity, location flexibility, company quality.

Return ONLY valid JSON:
{{
  "score": <integer 30-100>,
  "decision": "<ACCEPT|REVIEW|REJECT>",
  "reasoning": "<1-2 sentences>",
  "pros": ["<pro 1>", "<pro 2>"],
  "cons": ["<con 1>"],
  "required_skills": ["<skill 1>", "<skill 2>"],
  "missing_skills": ["<gap 1>" or ""]
}}"""
        
        messages = [{"role": "user", "content": prompt}]
        config = ModelConfig(model="openrouter", temperature=0.3, max_tokens=500)
        
        try:
            response = await provider.generate(messages, config)
            result = self._parse_gemini_response(response, opportunity)
            result.decision_path = "gemini_rerank"
            return result
        except Exception as e:
            logger.warning(f"Gemini rerank failed: {e}, falling back to deterministic")
            return self._deterministic_score(profile, opportunity, embedding_score)

    def _deterministic_score(
        self,
        profile: Profile,
        opportunity: Opportunity,
        embedding_score: int,
    ) -> HybridScoreResult:
        """Deterministic scoring based on skill gaps and signals.

        Args:
            profile: User profile
            opportunity: Opportunity to score
            embedding_score: Initial embedding score

        Returns:
            HybridScoreResult with deterministic scoring
        """
        required = self._extract_skills(opportunity.description or "")
        profile_skills = set(s.lower() for s in (profile.skills or []))
        required_lower = set(s.lower() for s in required)
        
        missing = [s for s in required if s.lower() not in profile_skills]
        gap_count = len(missing)
        skill_score = max(0, 100 - (gap_count * 10))
        
        # Recency boost: newer postings score higher
        recency_score = 100
        if opportunity.posted_at:
            days_old = (datetime.now(timezone.utc) - opportunity.posted_at).days
            recency_score = max(50, 100 - (days_old * 2))
        
        # Company signal
        company_score = 75  # Neutral
        if opportunity.company and any(
            keyword in opportunity.company.lower()
            for keyword in ["startup", "scale", "growth"]
        ):
            company_score = 85
        elif opportunity.company and any(
            keyword in opportunity.company.lower()
            for keyword in ["fortune", "enterprise", "bank"]
        ):
            company_score = 70
        
        # Combine: skill 50%, recency 30%, company 20%
        final_score = int(skill_score * 0.5 + recency_score * 0.3 + company_score * 0.2)
        
        return HybridScoreResult(
            opportunity_id=str(opportunity.id) if opportunity.id else None,
            title=opportunity.title or "N/A",
            company=opportunity.company or "N/A",
            relevance_score=final_score,
            decision_path="deterministic",
            reasoning=f"Skill gap: {gap_count} missing, Posted {days_old if opportunity.posted_at else '?'} days ago",
            pros=self._extract_pros(profile, opportunity),
            cons=self._extract_cons(profile, opportunity, missing),
            required_skills=required,
            missing_skills=missing,
        )

    def _extract_skills(self, text: str, limit: int = 5) -> list[str]:
        """Extract likely skill keywords from text."""
        common_skills = {
            "python", "javascript", "typescript", "java", "golang", "rust",
            "react", "vue", "angular", "django", "fastapi", "nodejs",
            "postgresql", "mongodb", "redis", "aws", "gcp", "docker",
            "kubernetes", "sql", "git", "agile", "scrum",
        }
        text_lower = text.lower()
        found = [s for s in common_skills if s in text_lower]
        return found[:limit]

    def _extract_pros(self, profile: Profile, opportunity: Opportunity) -> list[str]:
        """Extract positive signals."""
        pros = []
        
        # Skill match
        skills = set(s.lower() for s in (profile.skills or []))
        opp_text = f"{opportunity.title} {opportunity.description or ''}".lower()
        matched_skills = [s for s in skills if s in opp_text]
        if matched_skills:
            pros.append(f"Skills match: {', '.join(matched_skills[:2])}")
        
        # Recency
        if opportunity.posted_at:
            days_old = (datetime.now(timezone.utc) - opportunity.posted_at).days
            if days_old < 7:
                pros.append("Recently posted (within 7 days)")
        
        # Growth signals
        if opportunity.description and any(
            word in opportunity.description.lower()
            for word in ["growth", "learning", "mentorship", "opportunity"]
        ):
            pros.append("Growth and learning opportunity")
        
        return pros

    def _extract_cons(
        self,
        profile: Profile,
        opportunity: Opportunity,
        missing_skills: list[str],
    ) -> list[str]:
        """Extract negative signals."""
        cons = []
        
        if missing_skills:
            cons.append(f"Missing {len(missing_skills)} skills: {', '.join(missing_skills[:2])}")
        
        # Deadline soon
        if opportunity.deadline_at:
            days_to_deadline = (
                opportunity.deadline_at - datetime.now(timezone.utc)
            ).days
            if days_to_deadline < 3:
                cons.append("Application deadline approaching (< 3 days)")
        
        return cons

    def _format_profile_context(self, profile: Profile) -> str:
        """Format profile for LLM."""
        return f"""
Name: {profile.display_name or 'Unknown'}
Skills: {', '.join(profile.skills or [])}
Keywords: {', '.join(profile.keywords or [])}
Experience: {profile.experience_summary or 'Not provided'}
"""

    def _format_opportunity_context(self, opportunity: Opportunity) -> str:
        """Format opportunity for LLM."""
        return f"""
Title: {opportunity.title}
Company: {opportunity.company or 'Unknown'}
Posted: {opportunity.posted_at or 'Unknown'}
Deadline: {opportunity.deadline_at or 'Unknown'}
Description: {opportunity.description[:500] if opportunity.description else 'N/A'}
"""

    def _parse_gemini_response(
        self,
        response: Any,
        opportunity: Opportunity,
    ) -> HybridScoreResult:
        """Parse Gemini response into HybridScoreResult."""
        try:
            import json

            # Extract JSON from response
            text = getattr(response, "text", str(response))
            json_start = text.find("{")
            json_end = text.rfind("}") + 1
            json_str = text[json_start:json_end] if json_start >= 0 else "{}"
            
            data = json.loads(json_str)
            
            return HybridScoreResult(
                opportunity_id=str(opportunity.id) if opportunity.id else None,
                title=opportunity.title or "N/A",
                company=opportunity.company or "N/A",
                relevance_score=int(data.get("score", 50)),
                decision_path="gemini_rerank",
                reasoning=data.get("reasoning", ""),
                pros=data.get("pros", []),
                cons=data.get("cons", []),
                required_skills=data.get("required_skills", []),
                missing_skills=data.get("missing_skills", []),
            )
        except Exception as e:
            logger.error(f"Failed to parse Gemini response: {e}")
            return HybridScoreResult(
                opportunity_id=str(opportunity.id) if opportunity.id else None,
                title=opportunity.title or "N/A",
                company=opportunity.company or "N/A",
                relevance_score=50,
                decision_path="error",
                reasoning="LLM parsing failed",
                pros=[],
                cons=[],
                required_skills=[],
                missing_skills=[],
            )
