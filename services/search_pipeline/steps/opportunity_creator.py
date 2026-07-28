"""Pipeline step — creates/updates Opportunity DB records from search results."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from database.models.opportunities import Opportunity
from database.repositories.opportunity_repository import OpportunityRepository
from services.search_pipeline.date_parser import extract_metadata
from services.search_pipeline.dedup import is_duplicate_by_company_title, merge_sources
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

            # Stage 1: Dedup by exact URL (fast)
            if url:
                existing_by_url = self._find_by_url(profile.user_id, url)
                if existing_by_url is not None:
                    existing_by_url.last_seen_at = datetime.now(timezone.utc)
                    self._repo.update(existing_by_url)
                    opportunities.append(existing_by_url)
                    skipped += 1
                    continue

            # Extract structured metadata from description
            metadata = extract_metadata(description) if description else {}
            
            opp = Opportunity(
                user_id=profile.user_id,
                profile_id=profile.id,
                title=title[:500],
                description=description,
                url=url,
                source_type="search",
                company=metadata.get("company"),
                industry=None,  # Will be enriched later if needed
                posted_at=metadata.get("posted_at"),
                deadline_at=metadata.get("deadline_at"),
                application_deadline_raw=metadata.get("deadline_at"),  # For backward compat
                status="new",
                priority="medium",
                discovered_at=datetime.now(timezone.utc),
            )
            
            # Stage 2: Dedup by fuzzy match on (company, title) - catches same job from multiple boards
            existing_by_fuzzy = self._find_by_company_title(profile.user_id, profile.id, opp)
            if existing_by_fuzzy is not None:
                # Merge sources: add new URL to existing opportunity's metadata
                merge_sources(existing_by_fuzzy, opp)
                existing_by_fuzzy.last_seen_at = datetime.now(timezone.utc)
                self._repo.update(existing_by_fuzzy)
                opportunities.append(existing_by_fuzzy)
                skipped += 1
                logger.debug(f"Deduped fuzzy: {opp.title} @ {opp.company} (found existing with ID {existing_by_fuzzy.id})")
                continue
            
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

    def _find_by_company_title(self, user_id: Any, profile_id: Any, opportunity: Opportunity) -> Opportunity | None:
        """Find duplicate using fuzzy match on (company, title).

        Args:
            user_id: User ID to scope search
            profile_id: Profile ID to scope search
            opportunity: Opportunity with company and title to match

        Returns:
            Matching opportunity or None
        """
        # Get all opportunities for this user+profile
        all_opps = self._repo.list(user_id=user_id, profile_id=profile_id)
        
        # Check for fuzzy match
        if is_duplicate_by_company_title(opportunity, all_opps, similarity_threshold=0.85):
            # Find the first matching one (in production, could rank by score/recency)
            for existing in all_opps:
                if is_duplicate_by_company_title(opportunity, [existing], similarity_threshold=0.85):
                    return existing
        
        return None
