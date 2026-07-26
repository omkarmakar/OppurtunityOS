"""Pipeline step — AI-ranks opportunities against the user profile."""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from database.models.opportunities import Opportunity
from services.opportunity_scorer import OpportunityScorer
from services.search_pipeline.steps.base import PipelineStep

logger = logging.getLogger(__name__)


class AIRankingStep(PipelineStep):
    def __init__(
        self,
        db: Session,
        provider: str = "",
        model: str = "",
    ) -> None:
        self._db = db
        self._provider = provider
        self._model = model
        self._scorer = OpportunityScorer(
            provider_name=provider or None,
            model_name=model or None,
        )

    @property
    def name(self) -> str:
        return "AIRanking"

    async def execute(self, ctx: dict[str, Any]) -> dict[str, Any]:
        profile = ctx.get("profile")
        opportunities: list[Opportunity] = ctx.get("opportunities", [])

        if not profile or not opportunities:
            ctx["scored_opportunities"] = []
            return ctx

        try:
            scored = await self._scorer.score_multiple_and_save(profile, opportunities)
            self._db.flush()
            ctx["scored_opportunities"] = scored
        except Exception as e:
            logger.warning(f"AI ranking failed for {len(opportunities)} opportunities: {e}. Using fallback scores.")
            # If AI scoring fails, assign fallback scores based on keyword matching
            fallback_scored = []
            for opp in opportunities:
                from services.opportunity_scorer.scorer import ScoredOpportunity
                # Simple fallback: if profile keywords appear in opportunity, score 60, else 30
                score = 60 if any(kw.lower() in (opp.title or "").lower() for kw in (profile.keywords or [])) else 30
                fallback_scored.append(ScoredOpportunity(
                    opportunity_id=str(opp.id),
                    title=opp.title,
                    url=opp.url or "",
                    relevance_score=score,
                    summary=f"Fallback score: {score}/100",
                    pros=[],
                    cons=[],
                    required_skills=[],
                    missing_skills=[],
                    application_deadline=opp.application_deadline or "",
                    ranking_explanation="AI ranking unavailable, fallback scoring applied",
                ))
            ctx["scored_opportunities"] = fallback_scored

        return ctx
