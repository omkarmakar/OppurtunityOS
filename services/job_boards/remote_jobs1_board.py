"""Remote Jobs1 provider — remote ATS job listings via RapidAPI.

VERIFICATION COMMENT BLOCK (2026-07-29):
========================================
API: Remote Jobs (remote-jobs-remote-jobs-default)
Host: remote-jobs1.p.rapidapi.com
Secret key name: rapidapi_key (stored via core.secrets)

ENDPOINT — Get Remote Jobs (discovery)
  Method: GET
  Path: /jobs
  Optional params:
    - country (string) — 2-letter country code, e.g. "us"
    - employment_type (string) — "fulltime", "parttime", "contract", "internship"
    - limit (int) — max results, default 50
    - include_company (bool) — include company details
    - include_total_count (bool) — include total_count in response
    - cursor (int) — pagination cursor (from next_cursor in previous response)
  Response shape:
    { total_count (int), data: [ { id (int), slug, url, title, description (HTML),
      datePosted (ISO8601), skills, categories: [str], employmentTypes: [str],
      locationTypes: [str], countries: [str],
      company: { name, slug, website, linkedinUrl, linkedinSize, linkedinIndustry, ... }
    } ], next_cursor (int), has_more (bool) }
  Rate limit headers: x-ratelimit-remaining, x-ratelimit-limit, x-ratelimit-reset

SUPPORTED ATS PLATFORMS: Workable, Ashby, Lever, Greenhouse, Teamtailor,
SmartRecruiters, Recruitee, Breezy, Personio, JazzHR, JobScore, Rippling, and more.

LIVE TEST: Verified working (2026-07-29). Returns remote ATS job listings with company details.
"""

from __future__ import annotations

import logging
from typing import Any

from services.job_boards.base import JobPosting
from services.job_boards.rapidapi_base import RapidAPIJobBoard

logger = logging.getLogger(__name__)


class RemoteJobs1Board(RapidAPIJobBoard):
    """Remote Jobs1 — remote job listings from ATS platforms."""

    def __init__(self) -> None:
        super().__init__(
            name="remote_jobs",
            host="remote-jobs1.p.rapidapi.com",
            secret_name="rapidapi_key_remote_jobs",
        )

    async def search(self, queries: list[str], max_results: int = 50) -> list[JobPosting]:
        all_postings: list[JobPosting] = []

        params = {
            "limit": min(max_results, 50),
            "include_company": "true",
        }
        data = await self._get("/jobs", params)
        if not data or not isinstance(data, dict):
            return []

        jobs = data.get("data", [])
        if not isinstance(jobs, list):
            return []

        for job in jobs[:max_results]:
            posting = self._parse_job(job)
            if posting:
                all_postings.append(posting)

        return all_postings[:max_results]

    async def get_job_details(self, job_id: str) -> JobPosting | None:
        # Remote Jobs1 doesn't have a single-job endpoint,
        # but we can filter by the job's slug/id in the list
        data = await self._get("/jobs", {"limit": 50})
        if not data or not isinstance(data, dict):
            return None
        jobs = data.get("data", [])
        if not isinstance(jobs, list):
            return None
        for job in jobs:
            if str(job.get("id", "")) == str(job_id):
                return self._parse_job(job)
        return None

    def _parse_job(self, job: dict[str, Any]) -> JobPosting | None:
        if not isinstance(job, dict):
            return None

        title = job.get("title", "")
        job_id = job.get("id", "")
        url = job.get("url", "")

        if not title:
            return None

        # Company info
        company_data = job.get("company", {})
        company_name = company_data.get("name", "") if isinstance(company_data, dict) else ""

        # Location
        countries = job.get("countries", [])
        if not isinstance(countries, list):
            countries = []
        location_types = job.get("locationTypes", [])
        if not isinstance(location_types, list):
            location_types = []

        location = ""
        if "remote" in [lt.lower() for lt in location_types if isinstance(lt, str)]:
            location = "Remote"
        elif countries:
            location = ", ".join(c.upper() for c in countries if isinstance(c, str))

        # Skills
        skills = job.get("skills", [])
        if not isinstance(skills, list):
            skills = []

        # Employment type
        emp_types = job.get("employmentTypes", [])
        job_type = emp_types[0] if isinstance(emp_types, list) and emp_types else ""

        # Strip HTML from description
        description = job.get("description", "") or ""
        if "<" in description:
            import re
            description = re.sub(r"<[^>]+>", " ", description)
            description = re.sub(r"\s+", " ", description).strip()

        return self._map_to_posting(
            title=title,
            company=company_name,
            description=description[:2000],
            url=url,
            job_id=str(job_id),
            location=location,
            salary="",
            job_type=job_type,
            experience_required="",
            skills=[s for s in skills if isinstance(s, str)],
            posted_date=job.get("datePosted"),
            metadata={
                "source": "remote_jobs",
                "categories": job.get("categories", []),
                "location_types": location_types,
                "company_website": company_data.get("website", "") if isinstance(company_data, dict) else "",
                "company_linkedin": company_data.get("linkedinUrl", "") if isinstance(company_data, dict) else "",
                "company_industry": company_data.get("linkedinIndustry", "") if isinstance(company_data, dict) else "",
                "company_size": company_data.get("linkedinSize", "") if isinstance(company_data, dict) else "",
            },
        )
