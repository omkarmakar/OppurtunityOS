"""Base class for job board integrations."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class JobPosting:
    """Standardized job posting from any job board."""
    
    title: str
    company: str
    description: str
    url: str
    board: str  # "linkedin", "naukri", "unstop", etc.
    job_id: str  # Unique ID on that board
    location: str = ""
    salary: str = ""
    job_type: str = "Full-time"  # Full-time, Contract, Internship, etc.
    experience_required: str = ""
    skills: list[str] = field(default_factory=list)
    posted_date: datetime | None = None
    application_deadline: str = ""
    source_url: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


class JobBoard(ABC):
    """Abstract base class for job board scrapers."""
    
    def __init__(self, name: str):
        self.name = name
    
    @abstractmethod
    async def search(self, queries: list[str], max_results: int = 50) -> list[JobPosting]:
        """Search for jobs on this board given search queries.
        
        Args:
            queries: List of search queries
            max_results: Maximum results to return per query
            
        Returns:
            List of JobPosting objects
        """
        pass
    
    @abstractmethod
    async def get_job_details(self, job_id: str) -> JobPosting | None:
        """Get detailed information about a specific job posting.
        
        Args:
            job_id: The board-specific job ID
            
        Returns:
            Full JobPosting object or None if not found
        """
        pass
