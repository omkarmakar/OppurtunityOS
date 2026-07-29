"""Base class for RapidAPI job board providers with shared auth and quota tracking.

All RapidAPI providers share the same auth pattern (x-rapidapi-key header)
and similar rate-limit headers. This module centralizes that logic.

Per-provider secrets:
  Each provider can specify its own secret_name (e.g. "rapidapi_key_jsearch").
  If not found, falls back to the shared "rapidapi_key" secret.
"""

from __future__ import annotations

import logging
import time
from typing import Any

import httpx

from core.secrets import get_secret
from services.job_boards.base import JobBoard, JobPosting

logger = logging.getLogger(__name__)

RAPIDAPI_SECRET_NAME = "rapidapi_key"


class QuotaTracker:
    """Tracks API quota from response headers.

    Different RapidAPI providers use different header names for quota info.
    This class is configured per-provider with the correct header names.

    Quota state can be persisted via the database (see quota_repository.py)
    and restored via load_state()/save_state().
    """

    def __init__(
        self,
        remaining_header: str = "x-ratelimit-remaining",
        limit_header: str = "x-ratelimit-limit",
        reset_header: str = "x-ratelimit-reset",
    ) -> None:
        self.remaining_header = remaining_header
        self.limit_header = limit_header
        self.reset_header = reset_header
        self.remaining: int | None = None
        self.limit: int | None = None
        self.reset_at: float | None = None

    def update(self, headers: dict[str, str]) -> None:
        """Update quota from response headers."""
        try:
            val = headers.get(self.remaining_header)
            if val is not None:
                self.remaining = int(val)
        except (ValueError, TypeError):
            pass
        try:
            val = headers.get(self.limit_header)
            if val is not None:
                self.limit = int(val)
        except (ValueError, TypeError):
            pass
        try:
            val = headers.get(self.reset_header)
            if val is not None:
                self.reset_at = float(val)
        except (ValueError, TypeError):
            pass

    @property
    def is_exhausted(self) -> bool:
        return self.remaining is not None and self.remaining <= 0

    @property
    def seconds_until_reset(self) -> float:
        if self.reset_at is None:
            return 0.0
        return max(0.0, self.reset_at - time.time())

    def would_exhaust(self, cost: int = 1) -> bool:
        """Check if making `cost` requests would exhaust remaining quota."""
        if self.remaining is None:
            return False
        return self.remaining < cost

    def is_below_safety_margin(self, margin: float = 0.1) -> bool:
        """Check if remaining quota is below the safety margin fraction of limit."""
        if self.remaining is None or self.limit is None or self.limit == 0:
            return False
        return self.remaining < (self.limit * margin)

    def to_dict(self) -> dict[str, Any]:
        """Serialize for persistence."""
        return {
            "remaining": self.remaining,
            "limit": self.limit,
            "reset_at": self.reset_at,
        }

    def load_state(self, remaining: int | None, limit: int | None, reset_at: float | None) -> None:
        """Restore from persisted state."""
        self.remaining = remaining
        self.limit = limit
        self.reset_at = reset_at

    def __repr__(self) -> str:
        return (
            f"QuotaTracker(remaining={self.remaining}, "
            f"limit={self.limit}, reset_in={self.seconds_until_reset:.0f}s)"
        )


class RapidAPIJobBoard(JobBoard):
    """Base class for RapidAPI-backed job boards.

    Subclasses must set:
        - self._host: The RapidAPI host (e.g. "jsearch.p.rapidapi.com")

    Subclasses may set:
        - self._secret_name: Per-provider secret name (defaults to "rapidapi_key")

    And implement:
        - search(queries, max_results) -> list[JobPosting]
        - get_job_details(job_id) -> JobPosting | None
    """

    def __init__(
        self,
        name: str,
        host: str,
        secret_name: str = RAPIDAPI_SECRET_NAME,
        quota_remaining_header: str = "x-ratelimit-remaining",
        quota_limit_header: str = "x-ratelimit-limit",
        quota_reset_header: str = "x-ratelimit-reset",
    ) -> None:
        super().__init__(name)
        self._host = host
        self._secret_name = secret_name
        self._quota = QuotaTracker(
            remaining_header=quota_remaining_header,
            limit_header=quota_limit_header,
            reset_header=quota_reset_header,
        )

    @property
    def quota(self) -> QuotaTracker:
        """Expose quota tracker for external inspection (e.g. weekly scheduler)."""
        return self._quota

    def _get_api_key(self) -> str:
        """Retrieve the RapidAPI key from secrets store.

        Tries provider-specific secret first (e.g. "rapidapi_key_jsearch"),
        then falls back to the shared "rapidapi_key".
        """
        key = get_secret(self._secret_name)
        if key:
            return key
        # Fallback to shared key
        if self._secret_name != RAPIDAPI_SECRET_NAME:
            key = get_secret(RAPIDAPI_SECRET_NAME)
            if key:
                return key
        raise RuntimeError(
            f"No API key found for provider '{self._name}'. "
            f"Store one with: set_secret('{self._secret_name}', 'your-key')"
        )

    def _headers(self) -> dict[str, str]:
        return {
            "x-rapidapi-key": self._get_api_key(),
            "x-rapidapi-host": self._host,
            "Content-Type": "application/json",
        }

    async def _get(
        self,
        path: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any] | list[Any] | None:
        """Make an authenticated GET request to the RapidAPI endpoint.

        Returns the parsed JSON response body, or None on error.
        Updates quota tracker from response headers.
        """
        url = f"https://{self._host}{path}"
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(
                    url,
                    headers=self._headers(),
                    params=params or {},
                )
                self._quota.update(dict(resp.headers))

                if resp.status_code == 429:
                    logger.warning(
                        "%s: Rate limited (remaining=%s, reset_in=%.0fs). "
                        "URL: %s params=%s",
                        self.name,
                        self._quota.remaining,
                        self._quota.seconds_until_reset,
                        path,
                        params,
                    )
                    return None

                resp.raise_for_status()
                return resp.json()

        except httpx.HTTPStatusError as exc:
            logger.warning(
                "%s: HTTP %d for %s: %s",
                self.name,
                exc.response.status_code,
                path,
                exc.response.text[:200],
            )
            return None
        except Exception as exc:
            logger.warning("%s: Request failed for %s: %s", self.name, path, exc)
            return None

    def persist_quota(self, session) -> None:
        """Persist current quota state to the database.

        Call this after a batch of API calls to save the latest
        rate-limit headers for the weekly scheduler.
        """
        from database.repositories.quota_state_repository import QuotaStateRepository
        repo = QuotaStateRepository(session)
        repo.upsert(
            provider_name=self.name,
            remaining=self._quota.remaining,
            quota_limit=self._quota.limit,
            reset_at=self._quota.reset_at,
        )
        session.flush()

    def _map_to_posting(
        self,
        *,
        title: str,
        company: str,
        description: str,
        url: str,
        job_id: str,
        board: str | None = None,
        location: str = "",
        salary: str = "",
        job_type: str = "",
        experience_required: str = "",
        skills: list[str] | None = None,
        posted_date: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> JobPosting:
        """Helper to create a JobPosting with common field mapping."""
        parsed_date = None
        if posted_date:
            try:
                from datetime import datetime, timezone
                parsed_date = datetime.fromisoformat(
                    posted_date.replace("Z", "+00:00")
                )
            except (ValueError, TypeError):
                pass

        return JobPosting(
            title=title or "",
            company=company or "",
            description=description or "",
            url=url or "",
            board=board or self.name,
            job_id=job_id or "",
            location=location or "",
            salary=salary or "",
            job_type=job_type or "",
            experience_required=experience_required or "",
            skills=skills or [],
            posted_date=parsed_date,
            metadata=metadata or {},
        )
