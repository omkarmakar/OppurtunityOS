"""Real job board integrations for finding opportunities on LinkedIn, Naukri, Unstop, etc."""

from services.job_boards.aggregator import JobBoardAggregator
from services.job_boards.base import JobBoard, JobPosting
from services.job_boards.linkedin import LinkedInJobBoard
from services.job_boards.naukri import NaukriJobBoard
from services.job_boards.unstop import UnstopJobBoard

__all__ = [
    "JobBoard",
    "JobPosting",
    "LinkedInJobBoard",
    "NaukriJobBoard",
    "UnstopJobBoard",
    "JobBoardAggregator",
]
