"""Job board aggregator search provider wrapper.

On ad-hoc (user-initiated) searches, this provider reads from
already-stored Opportunities in the database — no live RapidAPI calls.
Live RapidAPI pulls are handled exclusively by the weekly scheduler
(services/background/tasks.py) or via an explicit search_live() call
gated behind a quota warning.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from services.search.provider import SearchProvider, SearchResult

logger = logging.getLogger(__name__)


def _query_matches(query: str, text: str) -> bool:
    """Check if a search query matches a text field (case-insensitive word match)."""
    if not query or not text:
        return False
    query_words = re.findall(r'\w+', query.lower())
    text_lower = text.lower()
    return all(w in text_lower for w in query_words)


class JobBoardProvider(SearchProvider):
    """Search provider that reads from stored job-board Opportunities.

    This does NOT make live RapidAPI calls. It queries the database
    for Opportunities already discovered by the weekly scheduler,
    filtering by the user's search query terms.
    """

    def __init__(self):
        super().__init__()
        self._name = "jobboards"

    @property
    def name(self) -> str:
        return self._name

    async def search(self, query: str, count: int = 10, offset: int = 0) -> list[SearchResult]:
        """Read stored job-board Opportunities matching the query.

        Returns Opportunities that were previously discovered by the
        weekly scheduler, filtered by the search query terms.
        """
        logger.info("JobBoardProvider.search (cached): %r", query)

        try:
            from backend.api.deps import get_db
            from database.models.opportunities import Opportunity

            db = next(get_db())
            # Fetch recent non-dummy opportunities (last 30 days)
            opps = (
                db.query(Opportunity)
                .filter(
                    Opportunity.source_type == "search",
                    Opportunity.url.notlike("%dummy%"),
                )
                .order_by(Opportunity.discovered_at.desc())
                .limit(200)
                .all()
            )

            # Filter by query terms
            results: list[SearchResult] = []
            for opp in opps:
                searchable = " ".join([
                    opp.title or "",
                    opp.company or "",
                    opp.description or "",
                    opp.url or "",
                ])
                if _query_matches(query, searchable):
                    results.append(SearchResult(
                        title=opp.title or "",
                        url=opp.url or "",
                        snippet=(opp.description or "")[:300],
                        source="jobboards",
                        raw={
                            "company": opp.company,
                            "id": str(opp.id),
                            "status": opp.status,
                            "priority": opp.priority,
                            "cached": True,
                        },
                    ))
                if len(results) >= count:
                    break

            logger.info(
                "JobBoardProvider: %d cached results for %r (from %d stored)",
                len(results), query, len(opps),
            )
            return results

        except Exception as e:
            logger.error("JobBoardProvider search failed: %s", e)
            return []

    async def search_live(
        self, query: str, count: int = 10, *, force: bool = False
    ) -> list[SearchResult]:
        """Explicit on-demand live pull from RapidAPI providers.

        This is NOT called by ad-hoc searches. It's for a dedicated
        "Search job boards now" action that checks quota first.

        Args:
            query: Search query.
            count: Max results.
            force: Skip quota check (for background scheduler use).

        Returns:
            Live results from RapidAPI providers.

        Raises:
            RuntimeError: If quota would be exhausted and force=False.
        """
        from services.job_boards import JobBoardAggregator
        from services.job_boards.rapidapi_base import QuotaTracker

        if not force:
            qt = QuotaTracker()
            if qt.would_exhaust(1):
                remaining = qt.remaining("shared")
                raise RuntimeError(
                    f"Job board API quota too low (remaining: {remaining}). "
                    f"Wait for quota reset or run the weekly sweep."
                )

        logger.info("JobBoardProvider.search_live (RapidAPI): %r", query)
        aggregator = JobBoardAggregator()
        postings = await aggregator.search_all([query], max_results_per_board=count)

        results = []
        for posting in postings[:count]:
            results.append(SearchResult(
                title=posting.title,
                url=posting.url,
                snippet=posting.description[:300] if posting.description else f"{posting.company} - {posting.job_type}",
                source=posting.board,
                raw={
                    "company": posting.company,
                    "location": posting.location,
                    "salary": posting.salary,
                    "job_type": posting.job_type,
                    "skills": posting.skills,
                    "experience_required": posting.experience_required,
                    "posted_date": posting.posted_date.isoformat() if posting.posted_date else None,
                    "application_deadline": posting.application_deadline,
                }
            ))

        logger.info("JobBoardProvider.search_live: %d results for %r", len(results), query)
        return results
