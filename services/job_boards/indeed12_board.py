"""Indeed12 provider — Indeed job search + company-targeted lookup via RapidAPI.

VERIFICATION COMMENT BLOCK (2026-07-29):
========================================
API: indeed12 (Mantiks)
Host: indeed12.p.rapidapi.com
Secret key name: rapidapi_key (stored via core.secrets)

ENDPOINT 1 — General Job Search (discovery)
  Method: GET
  Path: /jobs/search
  Required params: none (but query is recommended)
  Optional params:
    - locality (string) — Indeed country subdomain: "us", "uk", "de", etc. Default "us"
    - query (string) — job title/keyword search
    - location (string) — city or region
    - page_id (int) — pagination, starts at 1
  Response shape: Array of job objects with id field for detail lookup.
  Rate limit headers: x-ratelimit-remaining, x-ratelimit-limit, x-ratelimit-reset

ENDPOINT 2 — Company Jobs (company-targeted lookup)
  Method: GET
  Path: /company/{company_name}/jobs
  Required params: company_name (in URL path)
  Optional params:
    - locality (string) — "us", "uk", etc. Default "us"
    - start (int) — pagination offset, default 1
  Response shape: Array of job objects for that specific company.
  USE CASE: Company-site query tier — when target_companies is known.
  NOT for general discovery.

ENDPOINT 3 — Job Details (enrichment)
  Method: GET
  Path: /job/{job_id}
  Required params: job_id (in URL path)
  Optional params: locality (string)
  Response shape: Full job details with title, description, company, etc.

LIVE TEST: Requires separate RapidAPI subscription (returned 403 on 2026-07-29).
"""

from __future__ import annotations

import logging
from typing import Any

from services.job_boards.base import JobPosting
from services.job_boards.rapidapi_base import RapidAPIJobBoard

logger = logging.getLogger(__name__)


class Indeed12Board(RapidAPIJobBoard):
    """Indeed12 — Indeed job search + company-targeted lookup."""

    def __init__(self) -> None:
        super().__init__(
            name="indeed",
            host="indeed12.p.rapidapi.com",
            secret_name="rapidapi_key_indeed",
        )

    async def search(self, queries: list[str], max_results: int = 50) -> list[JobPosting]:
        """General job search via /jobs/search."""
        all_postings: list[JobPosting] = []

        for query in queries:
            params = {
                "locality": "us",
                "query": query,
                "page_id": 1,
            }
            data = await self._get("/jobs/search", params)
            if not data or not isinstance(data, list):
                continue

            for job in data[:max_results]:
                posting = self._parse_job(job)
                if posting:
                    all_postings.append(posting)

        return all_postings[:max_results]

    async def search_company(
        self, company_name: str, max_results: int = 50
    ) -> list[JobPosting]:
        """Company-targeted search via /company/{name}/jobs."""
        params = {
            "locality": "us",
            "start": 1,
        }
        path = f"/company/{company_name}/jobs"
        data = await self._get(path, params)
        if not data or not isinstance(data, list):
            return []

        postings = []
        for job in data[:max_results]:
            posting = self._parse_job(job)
            if posting:
                postings.append(posting)
        return postings

    async def get_job_details(self, job_id: str) -> JobPosting | None:
        params = {"locality": "us"}
        data = await self._get(f"/job/{job_id}", params)
        if not data or not isinstance(data, dict):
            return None
        return self._parse_job(data)

    def _parse_job(self, job: dict[str, Any]) -> JobPosting | None:
        if not isinstance(job, dict):
            return None

        title = job.get("title", "")
        job_id = job.get("id", job.get("job_id", ""))

        if not title:
            return None

        # Indeed detail page URL
        url = job.get("url", job.get("link", ""))
        if not url and job_id:
            url = f"https://www.indeed.com/viewjob?jk={job_id}"

        return self._map_to_posting(
            title=title,
            company=job.get("company", job.get("company_name", "")),
            description=job.get("description", job.get("snippet", ""))[:2000] or "",
            url=url,
            job_id=str(job_id),
            location=job.get("location", ""),
            salary=job.get("salary", ""),
            job_type=job.get("job_type", ""),
            experience_required="",
            skills=[],
            posted_date=job.get("date_posted", job.get("pub_date")),
            metadata={
                "source": "indeed",
                "locality": job.get("locality", "us"),
            },
        )
