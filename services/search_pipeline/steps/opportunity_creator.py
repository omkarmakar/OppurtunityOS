"""Pipeline step — creates/updates Opportunity DB records from search results."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from database.models.opportunities import Opportunity
from database.repositories.opportunity_repository import OpportunityRepository
from services.search_pipeline.steps.base import PipelineStep

logger = logging.getLogger(__name__)


class OpportunityCreator(PipelineStep):
    def __init__(self, db: Session) -> None:
        self._repo = OpportunityRepository(db)

    @property
    def name(self) -> str:
        return "OpportunityCreator"

    async def execute(self, ctx: dict[str, Any]) -> dict[str, Any]:
        extracted = ctx.get("extracted_contents", [])
        if not extracted:
            ctx["opportunities"] = []
            return ctx

        profile = ctx.get("profile")
        opportunities: list[Opportunity] = []
        skipped = 0

        for item in extracted:
            search_result = item.get("search_result")
            content = item.get("content")

            if not search_result:
                continue

            title = search_result.title or (content.title if content else "") or "Untitled"
            url = search_result.url or (content.source_url if content else "") or ""
            description = content.content if content and content.content else search_result.snippet

            # Dedup: skip if same (user_id, url) already exists
            if url:
                existing = self._find_by_url(profile.user_id, url)
                if existing is not None:
                    existing.last_seen_at = datetime.now(timezone.utc)
                    self._repo.update(existing)
                    opportunities.append(existing)
                    skipped += 1
                    continue

            opp = Opportunity(
                user_id=profile.user_id,
                title=title[:500],
                description=description,
                url=url,
                source_type="search",
                status="new",
                priority="medium",
                discovered_at=datetime.now(timezone.utc),
            )
            self._repo.add(opp)
            opportunities.append(opp)

        ctx["opportunities"] = opportunities
        ctx["opportunities_skipped_duplicate"] = skipped
        return ctx

    def _find_by_url(self, user_id: Any, url: str) -> Opportunity | None:
        matches = self._repo.list(user_id=user_id, url=url)
        if matches:
            return matches[0]
        return None
