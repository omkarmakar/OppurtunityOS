"""LinkedIn Job Search API provider — Fantastic.jobs job board listings via RapidAPI.

VERIFICATION COMMENT BLOCK (2026-07-29):
========================================
API: LinkedIn Job Search API (Fantastic.jobs)
Host: linkedin-job-search-api.p.rapidapi.com
Secret key name: rapidapi_key (stored via core.secrets)

ENDPOINT — Get Active Job Board Listings (discovery)
  Method: GET
  Path: /active-jb
  Required params: time_frame (string) — "1h", "24h", "7d", or "6m"
  Optional params:
    - limit (int) — default 100, max 1000
    - offset (int) — pagination
    - cursor (string) — cursor pagination (pass last job's id)
    - description_format (string) — "text" or "html" (omit to exclude)
    - title (string) — Google-style: "software engineer", "data OR engineer"
    - description (string) — Google-style on title+description
    - location (string) — Full names: "United States", OR syntax for multi
    - organization (string) — Exact, case-sensitive, comma-separated
    - date_posted_gte / date_posted_lt (string) — ISO 8601
    - direct_apply (string) — "only" or "exclude"
  Response shape: Array of ActiveJbJob objects:
    { id (int64), title, date_created, url, source, source_type: "jobboard",
      organization, date_posted, locations_derived: [str],
      description_text, ai_key_skills: [str], seniority, direct_apply,
      linkedin_id, org_linkedin_slug, ... }
  NOTE: org_linkedin_* fields are ALWAYS included on this endpoint
  (unlike active-ats where they're opt-in).
  Rate limit headers: x-ratelimit-remaining, x-ratelimit-limit, x-ratelimit-reset

LIVE TEST: Verified working (2026-07-29). Returns LinkedIn job board listings with org fields.
"""

from __future__ import annotations

import logging
from typing import Any

from services.job_boards.base import JobPosting
from services.job_boards.rapidapi_base import RapidAPIJobBoard

logger = logging.getLogger(__name__)


class LinkedInJobSearchBoard(RapidAPIJobBoard):
    """LinkedIn Job Search API — Fantastic.jobs LinkedIn job board listings."""

    def __init__(self) -> None:
        super().__init__(
            name="linkedin_jobs",
            host="linkedin-job-search-api.p.rapidapi.com",
            secret_name="rapidapi_key_linkedin_jobs",
        )

    async def search(self, queries: list[str], max_results: int = 50) -> list[JobPosting]:
        all_postings: list[JobPosting] = []

        for query in queries:
            params = {
                "time_frame": "24h",
                "limit": min(max_results, 100),
                "offset": 0,
                "description_format": "text",
                "title": query,
            }
            data = await self._get("/active-jb", params)
            if not data or not isinstance(data, list):
                continue

            for job in data[:max_results]:
                posting = self._parse_job(job)
                if posting:
                    all_postings.append(posting)

        return all_postings[:max_results]

    async def get_job_details(self, job_id: str) -> JobPosting | None:
        params = {
            "time_frame": "6m",
            "id": job_id,
            "description_format": "text",
        }
        data = await self._get("/active-jb", params)
        if not data or not isinstance(data, list) or not data:
            return None
        return self._parse_job(data[0])

    def _parse_job(self, job: dict[str, Any]) -> JobPosting | None:
        if not isinstance(job, dict):
            return None

        title = job.get("title", "")
        job_id = job.get("id", "")
        url = job.get("url", "")

        if not title or not job_id:
            return None

        # Location
        locations = job.get("locations_derived", [])
        if not isinstance(locations, list):
            locations = []
        location = locations[0] if locations else ""

        # Salary
        salary_min = job.get("ai_salary_min_value")
        salary_max = job.get("ai_salary_max_value")
        salary_currency = job.get("ai_salary_currency", "USD")
        salary_unit = job.get("ai_salary_unit_text", "YEAR")
        salary = ""
        if salary_min and salary_max:
            salary = f"{salary_currency} {salary_min:,.0f} - {salary_max:,.0f}/{salary_unit}"

        # Skills
        skills = job.get("ai_key_skills", [])
        if not isinstance(skills, list):
            skills = []

        # Employment type
        emp_types = job.get("ai_employment_type", [])
        if isinstance(emp_types, list) and emp_types:
            job_type = emp_types[0]
        else:
            job_type = ""

        return self._map_to_posting(
            title=title,
            company=job.get("organization", ""),
            description=job.get("description_text", "")[:2000] or "",
            url=url,
            job_id=str(job_id),
            location=location,
            salary=salary,
            job_type=job_type,
            experience_required=job.get("seniority", "") or job.get("ai_experience_level", ""),
            skills=[s for s in skills if isinstance(s, str)],
            posted_date=job.get("date_posted"),
            metadata={
                "source": job.get("source", ""),
                "source_type": "jobboard",
                "direct_apply": job.get("direct_apply", False),
                "linkedin_id": job.get("linkedin_id"),
                "org_linkedin_slug": job.get("org_linkedin_slug", ""),
                "org_linkedin_industry": job.get("org_linkedin_industry", ""),
                "org_linkedin_headcount": job.get("org_linkedin_headcount"),
                "work_arrangement": job.get("ai_work_arrangement", ""),
            },
        )
