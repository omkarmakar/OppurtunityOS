"""QuotaState repository — persists and retrieves per-provider API quota.

Used by the weekly scheduler to check remaining quota before firing
provider queries, and by RapidAPIJobBoard._get() to persist updated
quota after each API call.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select

from database.models.quota_state import QuotaState
from database.repositories.base import BaseRepository


class QuotaStateRepository(BaseRepository[QuotaState]):
    _model = QuotaState

    def get_by_provider(self, provider_name: str) -> QuotaState | None:
        """Return the quota state for a given provider, or None."""
        stmt = select(self._model).where(self._model.provider_name == provider_name)
        return self._session.scalar(stmt)

    def upsert(
        self,
        provider_name: str,
        remaining: int | None,
        quota_limit: int | None,
        reset_at: float | None,
    ) -> QuotaState:
        """Create or update quota state for a provider.

        Called after every RapidAPI response to persist the latest
        rate-limit headers.
        """
        existing = self.get_by_provider(provider_name)
        if existing is not None:
            existing.remaining = remaining
            existing.quota_limit = quota_limit
            existing.reset_at = reset_at
            existing.last_updated_at = datetime.now(timezone.utc)
            self._session.flush()
            return existing

        state = QuotaState(
            provider_name=provider_name,
            remaining=remaining,
            quota_limit=quota_limit,
            reset_at=reset_at,
        )
        self._session.add(state)
        self._session.flush()
        return state

    def get_all_providers(self) -> list[QuotaState]:
        """Return quota state for all tracked providers."""
        stmt = select(self._model).order_by(self._model.provider_name)
        return list(self._session.scalars(stmt))

    def is_below_safety_margin(
        self, provider_name: str, margin: float = 0.1,
    ) -> bool:
        """Check if a provider's remaining quota is below the safety margin.

        Returns True if remaining < limit * margin. Returns False if
        quota data is unavailable (provider hasn't been called yet).
        """
        state = self.get_by_provider(provider_name)
        if state is None or state.remaining is None or state.quota_limit is None or state.quota_limit == 0:
            return False
        return state.remaining < (state.quota_limit * margin)
