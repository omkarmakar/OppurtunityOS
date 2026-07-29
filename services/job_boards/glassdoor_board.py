"""Glassdoor Real-Time provider — job search + company interview enrichment via RapidAPI.

VERIFICATION COMMENT BLOCK (2026-07-29):
========================================
API: Real-Time Glassdoor Data (OpenWeb Ninja)
Host: real-time-glassdoor-data.p.rapidapi.com
Secret key name: rapidapi_key (stored via core.secrets)

ENDPOINT 1 — Job Search (discovery)
  Method: GET
  Path: /job-search
  Required params: query (string) — job title search
  Optional params:
    - location (string) — location filter
    - remote_only (bool) — filter remote jobs
    - easy_apply_only (bool) — only easy-apply jobs
    - min_company_rating (float) — minimum Glassdoor rating
    - page (int) — page number
    - domain (string) — Glassdoor domain, default "www.glassdoor.com"
  Response shape: Array of job objects:
    { job_id (int), job_title, company_id (int), company_name,
      company_logo (url), location, job_link (url), easy_apply (bool),
      rating (float), salary_min, salary_max, salary_median,
      salary_period, salary_source, age_in_days (int), ... }
  Rate limit headers: x-ratelimit-remaining, x-ratelimit-limit, x-ratelimit-reset

ENDPOINT 2 — Company Interviews (enrichment)
  Method: GET
  Path: /company-interviews
  Required params: company_id (int)
  Optional params: page, page_size, sort, job_function, job_title,
    location_type, received_offer_only, domain
  Response shape: Array of interview objects with questions, outcomes, etc.
  USE CASE: Attach interview insights to already-matched Opportunity's company.

NOTE: /interview-details is a single-interview lookup, not a search.
      Use /company-interviews for batch interview data.

LIVE TEST: Requires separate RapidAPI subscription (returned 403 on 2026-07-29).
"""

from __future__ import annotations

import logging
from typing import Any

from services.job_boards.base import JobPosting
from services.job_boards.rapidapi_base import RapidAPIJobBoard

logger = logging.getLogger(__name__)


class GlassdoorBoard(RapidAPIJobBoard):
    """Glassdoor Real-Time — job search + company interview enrichment."""

    def __init__(self) -> None:
        super().__init__(
            name="glassdoor",
            host="real-time-glassdoor-data.p.rapidapi.com",
            secret_name="rapidapi_key_glassdoor",
        )

    async def search(self, queries: list[str], max_results: int = 50) -> list[JobPosting]:
        all_postings: list[JobPosting] = []

        for query in queries:
            params = {
                "query": query,
                "page": 1,
            }
            data = await self._get("/job-search", params)
            if not data or not isinstance(data, dict):
                continue

            jobs = data.get("data", data.get("job_results", []))
            if not isinstance(jobs, list):
                continue

            for job in jobs[:max_results]:
                posting = self._parse_job(job)
                if posting:
                    all_postings.append(posting)

        return all_postings[:max_results]

    async def get_job_details(self, job_id: str) -> JobPosting | None:
        data = await self._get("/job-search", {"query": job_id, "page": 1})
        if not data or not isinstance(data, dict):
            return None
        jobs = data.get("data", data.get("job_results", []))
        if isinstance(jobs, list) and jobs:
            return self._parse_job(jobs[0])
        return None

    async def get_company_interviews(
        self, company_id: int, page: int = 1, page_size: int = 10
    ) -> list[dict[str, Any]]:
        """Get interview data for a company (enrichment, not discovery)."""
        params = {
            "company_id": company_id,
            "page": page,
            "page_size": page_size,
            "sort": "POPULAR",
        }
        data = await self._get("/company-interviews", params)
        if not data or not isinstance(data, dict):
            return []
        interviews = data.get("data", data.get("interviews", []))
        return interviews if isinstance(interviews, list) else []

    def _parse_job(self, job: dict[str, Any]) -> JobPosting | None:
        if not isinstance(job, dict):
            return None

        title = job.get("job_title", "")
        job_id = job.get("job_id", "")
        job_link = job.get("job_link", "")

        if not title:
            return None

        # Build job_id from int if needed
        str_id = str(job_id) if job_id else ""

        # Salary
        salary_min = job.get("salary_min")
        salary_max = job.get("salary_max")
        salary = ""
        if salary_min and salary_max:
            salary = f"${salary_min:,.0f} - ${salary_max:,.0f}"
        elif job.get("salary_median"):
            salary = f"~${job['salary_median']:,.0f}"

        # Posted date
        posted_date = None
        age_days = job.get("age_in_days")
        if age_days and isinstance(age_days, (int, float)):
            try:
                from datetime import datetime, timezone, timedelta
                posted_date = (datetime.now(timezone.utc) - timedelta(days=int(age_days))).isoformat()
            except (ValueError, TypeError):
                pass

        return self._map_to_posting(
            title=title,
            company=job.get("company_name", ""),
            description="",  # Glassdoor job-search doesn't return descriptions
            url=job_link or "",
            job_id=str_id,
            location=job.get("location", ""),
            salary=salary,
            job_type="",
            experience_required="",
            skills=[],
            posted_date=posted_date,
            metadata={
                "company_id": job.get("company_id"),
                "company_logo": job.get("company_logo", ""),
                "rating": job.get("rating"),
                "easy_apply": job.get("easy_apply", False),
                "salary_source": job.get("salary_source", ""),
                "source": "glassdoor",
            },
        )
