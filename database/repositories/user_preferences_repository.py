"""Repository for UserPreferences database operations."""

from __future__ import annotations

from typing import Any, Optional

from sqlalchemy.orm import Session

from database.models.user_preferences import UserPreferences
from database.repositories.base import BaseRepository


class UserPreferencesRepository(BaseRepository):
    """Handles UserPreferences database CRUD operations."""

    model = UserPreferences

    def get_by_user_id(self, user_id: str) -> Optional[UserPreferences]:
        """Get preferences for a user, creating defaults if needed."""
        prefs = self._session.query(UserPreferences).filter_by(user_id=user_id).first()
        if not prefs:
            prefs = UserPreferences(user_id=user_id)
            self.add(prefs)
        return prefs

    def update_scoring_weights(
        self,
        user_id: str,
        skill_gap: float,
        recency: float,
        company: float,
    ) -> UserPreferences:
        """Update scoring weights for a user."""
        prefs = self.get_by_user_id(user_id)
        prefs.scoring_skill_gap_weight = skill_gap
        prefs.scoring_recency_weight = recency
        prefs.scoring_company_weight = company
        
        is_valid, msg = prefs.validate_weights()
        if not is_valid:
            raise ValueError(f"Invalid weights: {msg}")
        
        self.update(prefs)
        return prefs

    def update_embedding_thresholds(
        self,
        user_id: str,
        accept: float,
        reject: float,
    ) -> UserPreferences:
        """Update embedding filter thresholds."""
        prefs = self.get_by_user_id(user_id)
        prefs.embedding_accept_threshold = accept
        prefs.embedding_reject_threshold = reject
        
        is_valid, msg = prefs.validate_thresholds()
        if not is_valid:
            raise ValueError(f"Invalid thresholds: {msg}")
        
        self.update(prefs)
        return prefs

    def update_notification_preferences(
        self,
        user_id: str,
        channels: list[str],
        digest_min_score: int,
        instant_alert_min_score: int,
    ) -> UserPreferences:
        """Update notification preferences."""
        prefs = self.get_by_user_id(user_id)
        prefs.notification_channels = channels
        prefs.digest_min_score_threshold = digest_min_score
        prefs.instant_alert_min_score = instant_alert_min_score
        self.update(prefs)
        return prefs

    def update_display_preferences(
        self,
        user_id: str,
        sort_by: str,
        items_per_page: int,
        show_unmatched: bool,
    ) -> UserPreferences:
        """Update display preferences."""
        prefs = self.get_by_user_id(user_id)
        prefs.list_sort_by = sort_by
        prefs.items_per_page = items_per_page
        prefs.show_unmatched_opportunities = show_unmatched
        self.update(prefs)
        return prefs

    def update_search_preferences(
        self,
        user_id: str,
        job_boards: Optional[list[str]] = None,
        results_per_query: int = 100,
    ) -> UserPreferences:
        """Update search behavior preferences."""
        prefs = self.get_by_user_id(user_id)
        if job_boards is not None:
            prefs.preferred_job_boards = job_boards
        prefs.search_results_per_query = results_per_query
        self.update(prefs)
        return prefs

    def update_llm_preferences(
        self,
        user_id: str,
        enable_reranking: bool,
        provider: str,
        model: Optional[str] = None,
    ) -> UserPreferences:
        """Update LLM backend preferences."""
        prefs = self.get_by_user_id(user_id)
        prefs.enable_llm_reranking = enable_reranking
        prefs.llm_provider = provider
        prefs.llm_model = model
        self.update(prefs)
        return prefs

    def reset_to_defaults(self, user_id: str) -> UserPreferences:
        """Reset preferences to defaults."""
        prefs = self.get_by_user_id(user_id)
        # Create a new default instance and copy values
        defaults = UserPreferences(user_id=user_id)
        for col in UserPreferences.__table__.columns:
            if col.name not in ("id", "user_id", "created_at"):
                setattr(prefs, col.name, getattr(defaults, col.name))
        self.update(prefs)
        return prefs
