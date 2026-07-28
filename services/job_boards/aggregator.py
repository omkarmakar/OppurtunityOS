"""Job board aggregator that combines results from multiple job sources."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from services.job_boards.base import JobBoard, JobPosting
from services.job_boards.linkedin import LinkedInJobBoard
from services.job_boards.naukri import NaukriJobBoard
from services.job_boards.unstop import UnstopJobBoard

logger = logging.getLogger(__name__)


class JobBoardAggregator:
    """Aggregates job postings from multiple job boards."""
    
    def __init__(self, boards: list[JobBoard] | None = None):
        """Initialize with job boards to use.
        
        Args:
            boards: List of JobBoard instances to aggregate. If None, uses default set.
        """
        if boards is None:
            boards = [
                LinkedInJobBoard(),
                NaukriJobBoard(),
                UnstopJobBoard(),
            ]
        self.boards = {board.name: board for board in boards}
    
    async def search_all(self, queries: list[str], max_results_per_board: int = 50) -> list[JobPosting]:
        """Search all configured job boards concurrently.
        
        Args:
            queries: List of search queries
            max_results_per_board: Maximum results per board per query
            
        Returns:
            Combined deduplicated list of JobPosting objects
        """
        logger.info(f"Starting aggregate search with {len(self.boards)} boards for {len(queries)} queries")
        
        # Create search tasks for all boards concurrently
        tasks = []
        for board in self.boards.values():
            task = board.search(queries, max_results=max_results_per_board)
            tasks.append(task)
        
        # Run all searches concurrently
        try:
            results = await asyncio.gather(*tasks, return_exceptions=True)
        except Exception as e:
            logger.error(f"Error during concurrent search: {e}")
            results = []
        
        # Aggregate and deduplicate results
        all_postings = []
        for result in results:
            if isinstance(result, Exception):
                logger.warning(f"Board search failed: {result}")
                continue
            if isinstance(result, list):
                all_postings.extend(result)
        
        # Deduplicate by job URL and title combination
        seen = set()
        unique_postings = []
        for posting in all_postings:
            key = (posting.url, posting.title)
            if key not in seen:
                seen.add(key)
                unique_postings.append(posting)
        
        logger.info(f"Aggregate search returned {len(unique_postings)} deduplicated postings from {len(self.boards)} boards")
        return unique_postings
    
    def get_board(self, name: str) -> JobBoard | None:
        """Get a specific job board by name."""
        return self.boards.get(name.lower())
    
    def add_board(self, board: JobBoard) -> None:
        """Add a new job board to the aggregator."""
        self.boards[board.name] = board
        logger.info(f"Added job board: {board.name}")
    
    async def search_single_board(self, board_name: str, queries: list[str], max_results: int = 50) -> list[JobPosting]:
        """Search a specific job board."""
        board = self.get_board(board_name)
        if not board:
            logger.warning(f"Job board not found: {board_name}")
            return []
        
        logger.info(f"Searching {board_name} with {len(queries)} queries")
        return await board.search(queries, max_results=max_results)
