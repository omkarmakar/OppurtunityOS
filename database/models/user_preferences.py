"""User preference customization model for granular control over app experience."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional
from uuid import uuid4

from sqlalchemy import Float, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from database.base import Base


class UserPreferences(Base):
    """User customization preferences for scoring, search, notifications, and UI.
    
    Provides selective freedom for users to customize:
    - Scoring weights (skill gap, recency, company signals)
    - Search behavior (job boards, backends)
    - Notification channels and thresholds
    - Display and sorting preferences
    """

    __tablename__ = "user_preferences"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)

    # Scoring weights (0-100, should sum to 100)
    scoring_skill_gap_weight: Mapped[float] = mapped_column(Float, default=50.0)
    scoring_recency_weight: Mapped[float] = mapped_column(Float, default=30.0)
    scoring_company_weight: Mapped[float] = mapped_column(Float, default=20.0)

    # Embedding filter thresholds
    embedding_accept_threshold: Mapped[float] = mapped_column(Float, default=75.0)
    embedding_reject_threshold: Mapped[float] = mapped_column(Float, default=25.0)

    # Scoring method preference
    scoring_method: Mapped[str] = mapped_column(
        String(50), default="hybrid", nullable=False,
    )

    # Search behavior
    preferred_job_boards: Mapped[Optional[list[str]]] = mapped_column(
        JSON, default=None, nullable=True,
    )
    search_results_per_query: Mapped[int] = mapped_column(default=100)

    # Scoring backends
    enable_llm_reranking: Mapped[bool] = mapped_column(default=True)
    llm_provider: Mapped[str] = mapped_column(String(50), default="openrouter")
    llm_model: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)

    # Notification preferences
    notification_channels: Mapped[Optional[list[str]]] = mapped_column(
        JSON, default=None, nullable=True,
    )
    digest_min_score_threshold: Mapped[int] = mapped_column(default=50)
    instant_alert_min_score: Mapped[int] = mapped_column(default=80)

    # Display preferences
    list_sort_by: Mapped[str] = mapped_column(
        String(50), default="score_desc", nullable=False,
    )
    items_per_page: Mapped[int] = mapped_column(default=20)
    show_unmatched_opportunities: Mapped[bool] = mapped_column(default=False)

    # Enrichment preferences
    enable_company_enrichment: Mapped[bool] = mapped_column(default=True)
    enable_role_analysis: Mapped[bool] = mapped_column(default=True)

    # Advanced options
    fallback_order: Mapped[Optional[str]] = mapped_column(
        String(500), nullable=True,
    )
    custom_notes: Mapped[Optional[str]] = mapped_column(default=None, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(timezone.utc), nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    def validate_weights(self) -> tuple[bool, str]:
        """Validate that scoring weights sum to approximately 100."""
        total = (
            self.scoring_skill_gap_weight
            + self.scoring_recency_weight
            + self.scoring_company_weight
        )
        if abs(total - 100.0) > 0.1:
            return False, f"Weights must sum to 100, got {total}"
        return True, ""

    def validate_thresholds(self) -> tuple[bool, str]:
        """Validate embedding filter thresholds."""
        if not (0 <= self.embedding_reject_threshold <= 50):
            return False, "reject_threshold must be 0-50"
        if not (50 <= self.embedding_accept_threshold <= 100):
            return False, "accept_threshold must be 50-100"
        if self.embedding_reject_threshold >= self.embedding_accept_threshold:
            return False, "reject_threshold must be < accept_threshold"
        return True, ""

    def to_dict(self) -> dict[str, Any]:
        """Convert preferences to dictionary for API responses."""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "scoring": {
                "skill_gap_weight": self.scoring_skill_gap_weight,
                "recency_weight": self.scoring_recency_weight,
                "company_weight": self.scoring_company_weight,
                "method": self.scoring_method,
            },
            "embedding_filter": {
                "accept_threshold": self.embedding_accept_threshold,
                "reject_threshold": self.embedding_reject_threshold,
            },
            "search": {
                "preferred_boards": self.preferred_job_boards or [],
                "results_per_query": self.search_results_per_query,
            },
            "scoring_backend": {
                "llm_reranking_enabled": self.enable_llm_reranking,
                "llm_provider": self.llm_provider,
                "llm_model": self.llm_model,
            },
            "notifications": {
                "channels": self.notification_channels or [],
                "digest_min_score": self.digest_min_score_threshold,
                "instant_alert_min_score": self.instant_alert_min_score,
            },
            "display": {
                "sort_by": self.list_sort_by,
                "items_per_page": self.items_per_page,
                "show_unmatched": self.show_unmatched_opportunities,
            },
            "enrichment": {
                "company_enrichment": self.enable_company_enrichment,
                "role_analysis": self.enable_role_analysis,
            },
            "advanced": {
                "fallback_order": self.fallback_order,
                "custom_notes": self.custom_notes,
            },
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }
