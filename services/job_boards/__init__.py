"""Real job board integrations for finding opportunities on LinkedIn, Naukri, Unstop, etc."""

from services.job_boards.active_jobs_db_board import ActiveJobsDBBoard
from services.job_boards.aggregator import JobBoardAggregator
from services.job_boards.base import JobBoard, JobPosting
from services.job_boards.glassdoor_board import GlassdoorBoard
from services.job_boards.indeed12_board import Indeed12Board
from services.job_boards.jsearch_board import JSearchBoard
from services.job_boards.linkedin import LinkedInJobBoard
from services.job_boards.linkedin_job_search_board import LinkedInJobSearchBoard
from services.job_boards.naukri import NaukriJobBoard
from services.job_boards.remote_jobs1_board import RemoteJobs1Board
from services.job_boards.unstop import UnstopJobBoard

__all__ = [
    "JobBoard",
    "JobPosting",
    "ActiveJobsDBBoard",
    "GlassdoorBoard",
    "Indeed12Board",
    "JSearchBoard",
    "LinkedInJobBoard",
    "LinkedInJobSearchBoard",
    "NaukriJobBoard",
    "RemoteJobs1Board",
    "UnstopJobBoard",
    "JobBoardAggregator",
]
