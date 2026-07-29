"""Active Jobs DB provider — Fantastic.jobs ATS listings via RapidAPI.

VERIFICATION COMMENT BLOCK (2026-07-29):
========================================
API: Active Jobs DB (Fantastic.jobs)
Host: active-jobs-db.p.rapidapi.com
Secret key name: rapidapi_key (stored via core.secrets)

ENDPOINT — Get Jobs (discovery)
  Method: GET
  Path: /active-ats
  Required params: time_frame (string) — "1h", "24h", "7d" (for weekly), or "6m"
  Optional params:
    - limit (int) — default 100, max 1000
    - offset (int) — pagination
    - cursor (string) — cursor-based pagination (overrides offset)
    - description_format (string) — "text" or "html" (omit to exclude description)
    - title (string) — Google-style: "software engineer", "data OR engineer"
    - description (string) — Google-style search on title+description
    - location (string) — Full names only: "United States", NOT "US"
      Multi-location with OR: "United States OR United Kingdom"
    - organization (string) — Exact, case-sensitive, comma-separated
    - organization_advanced (string) — Boolean search on org name
    - date_posted_gte (string) — ISO 8601 date
    - date_posted_lt (string) — ISO 8601 date
    - ai_experience_level (string) — "0-2", "2-5", "5-10", "10+"
    - ai_work_arrangement (string) — "Remote Solely", "Remote OK", "Hybrid", "On-site"
    - ai_employment_type (string) — "FULL_TIME", "PART_TIME", "CONTRACTOR", etc.
    - has_salary (bool) — only jobs with salary info
    - include_basic_organization_details (bool) — include LinkedIn company fields
  Response shape: Array of ActiveAtsJob objects:
    { id (int64), title, date_created, url, source, source_type: "ats",
      organization, date_posted, locations_derived: [str],
      description_text, ai_key_skills: [str], ai_experience_level,
      ai_work_arrangement, ai_employment_type: [str], ... }
  Rate limit headers: x-ratelimit-remaining, x-ratelimit-limit, x-ratelimit-reset

LIVE TEST: Verified working (2026-07-29). Returns ATS job listings with skills, experience level, work arrangement.
"""

from __future__ import annotations

import logging
from typing import Any

from services.job_boards.base import JobPosting
from services.job_boards.rapidapi_base import RapidAPIJobBoard

logger = logging.getLogger(__name__)


class ActiveJobsDBBoard(RapidAPIJobBoard):
    """Active Jobs DB — Fantastic.jobs ATS job listings."""

    def __init__(self) -> None:
        super().__init__(
            name="active_jobs_db",
            host="active-jobs-db.p.rapidapi.com",
            secret_name="rapidapi_key_active_jobs_db",
        )

    async def search(self, queries: list[str], max_results: int = 50) -> list[JobPosting]:
        all_postings: list[JobPosting] = []

        for query in queries:
            params = {
                "time_frame": "7d",
                "limit": min(max_results, 100),
                "offset": 0,
                "description_format": "text",
                "title": f'"{query}"',
            }
            data = await self._get("/active-ats", params)
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
        data = await self._get("/active-ats", params)
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

        # Location from derived fields
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
        elif job.get("ai_salary_value"):
            salary = f"{salary_currency} {job['ai_salary_value']:,.0f}/{salary_unit}"

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
            experience_required=job.get("ai_experience_level", ""),
            skills=[s for s in skills if isinstance(s, str)],
            posted_date=job.get("date_posted"),
            metadata={
                "source": job.get("source", ""),
                "source_type": job.get("source_type", ""),
                "work_arrangement": job.get("ai_work_arrangement", ""),
                "experience_level": job.get("ai_experience_level", ""),
                "visa_sponsorship": job.get("ai_visa_sponsorship"),
                "benefits": job.get("ai_benefits", []),
                "education": job.get("ai_education", []),
            },
        )
