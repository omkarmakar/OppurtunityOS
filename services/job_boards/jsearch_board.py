"""JSearch provider — Google for Jobs aggregator via RapidAPI.

VERIFICATION COMMENT BLOCK (2026-07-29):
========================================
API: JSearch (OpenWeb Ninja)
Host: jsearch.p.rapidapi.com
Secret key name: rapidapi_key (stored via core.secrets)

ENDPOINT 1 — Job Search (discovery)
  Method: GET
  Path: /search-v2-v2
  Required params: query (string) — free-form, include title + location
  Optional params:
    - page (int) — page number, default 1
    - num_pages (int) — max pages to return, default 1
    - country (string) — 2-letter country code, e.g. "us", "de"
    - language (string) — language code
    - location (string) — Google UULE location string
    - date_posted (string) — "all", "today", "3days", "week", "month"
    - employment_types (string) — comma-delimited: "FULLTIME,PARTTIME,CONTRACTOR"
    - job_requirements (string) — comma-delimited: "under_3_years_experience,more_than_3_years_experience,no_experience,no_degree"
    - fields (string) — comma-delimited field projection
  Response shape:
    { status: "OK", data: [ { job_id, job_title, employer_name, employer_url,
      job_description, job_apply_link, job_city, job_state, job_country,
      job_posted_at_timestamp, job_employment_type, ... } ], page: 1, num_pages: 1 }
  Rate limit headers: x-ratelimit-remaining, x-ratelimit-limit, x-ratelimit-reset

ENDPOINT 2 — Job Details (enrichment)
  Method: GET
  Path: /job-details
  Required params: job_id (string)
  Optional params: country (string), language (string), fields (string)
  Response shape: Same as search but single object in data array, with additional
    fields: employer_reviews, employer_rating, estimated_salaries, similar_jobs

LIVE TEST: Verified working (2026-07-29). Returns jobs from Google for Jobs aggregation.
"""

from __future__ import annotations

import logging
from typing import Any

from services.job_boards.base import JobPosting
from services.job_boards.rapidapi_base import RapidAPIJobBoard

logger = logging.getLogger(__name__)


class JSearchBoard(RapidAPIJobBoard):
    """JSearch — aggregates jobs from Google for Jobs (Indeed, LinkedIn, ZipRecruiter, etc.)."""

    def __init__(self) -> None:
        super().__init__(
            name="jsearch",
            host="jsearch.p.rapidapi.com",
            secret_name="rapidapi_key_jsearch",
        )

    async def search(self, queries: list[str], max_results: int = 50) -> list[JobPosting]:
        all_postings: list[JobPosting] = []
        per_query = max(1, max_results // max(1, len(queries)))

        for query in queries:
            params = {
                "query": query,
                "num_pages": 1,
                "page": 1,
            }
            data = await self._get("/search-v2", params)
            if not data or not isinstance(data, dict):
                continue

            # v2 nests jobs under data.jobs
            inner = data.get("data", data)
            jobs = inner.get("jobs", []) if isinstance(inner, dict) else []
            if not isinstance(jobs, list):
                continue

            for job in jobs[:per_query]:
                posting = self._parse_job(job)
                if posting:
                    all_postings.append(posting)

        return all_postings[:max_results]

    async def get_job_details(self, job_id: str) -> JobPosting | None:
        data = await self._get("/job-details", {"job_id": job_id})
        if not data or not isinstance(data, dict):
            return None

        inner = data.get("data", data)
        jobs = inner.get("data", []) if isinstance(inner, dict) else inner
        if isinstance(jobs, list) and jobs:
            return self._parse_job(jobs[0])
        return None

    def _parse_job(self, job: dict[str, Any]) -> JobPosting | None:
        if not isinstance(job, dict):
            return None

        title = job.get("job_title", "")
        employer = job.get("employer_name", "")
        description = job.get("job_description", "")
        apply_link = job.get("job_apply_link", "")
        job_id = job.get("job_id", "")

        if not title or not job_id:
            return None

        # Build location string
        city = job.get("job_city", "")
        state = job.get("job_state", "")
        country = job.get("job_country", "")
        location_parts = [p for p in [city, state, country] if p]
        location = ", ".join(location_parts)

        # Salary
        salary_min = job.get("job_min_salary")
        salary_max = job.get("job_max_salary")
        salary = ""
        if salary_min and salary_max:
            salary = f"${salary_min:,.0f} - ${salary_max:,.0f}"
        elif salary_min:
            salary = f"From ${salary_min:,.0f}"

        # Posted date from timestamp
        posted_at = None
        ts = job.get("job_posted_at_timestamp")
        if ts:
            try:
                from datetime import datetime, timezone
                posted_at = datetime.fromtimestamp(ts, tz=timezone.utc)
            except (ValueError, TypeError, OSError):
                pass

        # Skills from required technologies
        skills = job.get("job_required_technologies", [])
        if not isinstance(skills, list):
            skills = []

        return self._map_to_posting(
            title=title,
            company=employer,
            description=description[:2000] if description else "",
            url=apply_link or f"https://jsearch.p.rapidapi.com/job/{job_id}",
            job_id=str(job_id),
            location=location,
            salary=salary,
            job_type=job.get("job_employment_type", ""),
            experience_required=job.get("job_required_experience", ""),
            skills=[s for s in skills if isinstance(s, str)],
            posted_date=posted_at.isoformat() if posted_at else None,
            metadata={
                "publisher": job.get("job_publisher", ""),
                "is_remote": job.get("job_is_remote", False),
                "employer_url": job.get("employer_url", ""),
                "employer_logo": job.get("employer_logo", ""),
            },
        )
