"""Job board aggregator search provider wrapper."""

from __future__ import annotations

import logging
from typing import Any

from services.job_boards import JobBoardAggregator
from services.search.provider import SearchProvider, SearchResult

logger = logging.getLogger(__name__)


class JobBoardProvider(SearchProvider):
    """Search provider that aggregates real job board results."""
    
    def __init__(self):
        super().__init__()
        self._name = "jobboards"
        self._aggregator = JobBoardAggregator()
    
    @property
    def name(self) -> str:
        return self._name
    
    async def search(self, query: str, count: int = 10) -> list[SearchResult]:
        """Search multiple job boards for opportunities.
        
        Args:
            query: Search query for jobs
            count: Maximum number of results to return
            
        Returns:
            List of SearchResult objects from job boards
        """
        logger.info(f"Searching job boards for: {query}")
        
        try:
            # Search all boards with this single query
            postings = await self._aggregator.search_all([query], max_results_per_board=count)
            
            # Convert JobPosting objects to SearchResult objects
            results = []
            for posting in postings[:count]:
                result = SearchResult(
                    title=posting.title,
                    url=posting.url,
                    snippet=posting.description[:300] if posting.description else f"{posting.company} - {posting.job_type}",
                    source=posting.board,
                    metadata={
                        "company": posting.company,
                        "location": posting.location,
                        "salary": posting.salary,
                        "job_type": posting.job_type,
                        "skills": posting.skills,
                        "experience_required": posting.experience_required,
                        "posted_date": posting.posted_date.isoformat() if posting.posted_date else None,
                        "application_deadline": posting.application_deadline,
                    }
                )
                results.append(result)
            
            logger.info(f"Job board search returned {len(results)} results for '{query}'")
            return results
            
        except Exception as e:
            logger.error(f"Job board search failed for '{query}': {e}")
            return []
