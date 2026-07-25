"""Pipeline step — AI-ranks opportunities against the user profile."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from database.models.opportunities import Opportunity
from services.opportunity_scorer import OpportunityScorer
from services.search_pipeline.steps.base import PipelineStep


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
            provider_name=provider,
            model_name=model,
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

        scored = await self._scorer.score_multiple_and_save(profile, opportunities)
        self._db.flush()

        ctx["scored_opportunities"] = scored
        return ctx
