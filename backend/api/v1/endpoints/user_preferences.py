"""User preferences endpoints for customization of app experience."""

from __future__ import annotations

from typing import Any

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.api.deps import get_db
from database.repositories.user_preferences_repository import UserPreferencesRepository

router = APIRouter(prefix="/user-preferences", tags=["user-preferences"])


# Request/Response Models
class ScoringWeightsUpdate(BaseModel):
    """Scoring weights update request."""

    skill_gap_weight: float = Field(50.0, ge=0, le=100)
    recency_weight: float = Field(30.0, ge=0, le=100)
    company_weight: float = Field(20.0, ge=0, le=100)


class EmbeddingThresholdsUpdate(BaseModel):
    """Embedding filter thresholds update."""

    accept_threshold: float = Field(75.0, ge=50, le=100)
    reject_threshold: float = Field(25.0, ge=0, le=50)


class NotificationPreferencesUpdate(BaseModel):
    """Notification preferences update."""

    channels: list[str] = Field(default=["in_app", "email"])
    digest_min_score: int = Field(50, ge=0, le=100)
    instant_alert_min_score: int = Field(80, ge=0, le=100)


class DisplayPreferencesUpdate(BaseModel):
    """Display preferences update."""

    sort_by: str = Field("score_desc")
    items_per_page: int = Field(20, ge=1, le=100)
    show_unmatched: bool = False


class SearchPreferencesUpdate(BaseModel):
    """Search preferences update."""

    preferred_job_boards: list[str] = Field(default=[])
    results_per_query: int = Field(100, ge=1, le=1000)


class LLMPreferencesUpdate(BaseModel):
    """LLM backend preferences update."""

    enable_reranking: bool = True
    provider: str = "openrouter"
    model: str | None = None


class UserPreferencesResponse(BaseModel):
    """Complete user preferences response."""

    id: str
    user_id: str
    scoring: dict[str, Any]
    embedding_filter: dict[str, Any]
    search: dict[str, Any]
    scoring_backend: dict[str, Any]
    notifications: dict[str, Any]
    display: dict[str, Any]
    enrichment: dict[str, Any]
    advanced: dict[str, Any]
    created_at: str
    updated_at: str


@router.get("/user/{user_id}", response_model=UserPreferencesResponse)
async def get_user_preferences(
    user_id: UUID,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Get user's preferences with all customization options."""
    repo = UserPreferencesRepository(db)
    prefs = repo.get_by_user_id(str(user_id))
    return prefs.to_dict()


@router.patch("/user/{user_id}/scoring-weights", response_model=UserPreferencesResponse)
async def update_scoring_weights(
    user_id: UUID,
    update: ScoringWeightsUpdate,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Update scoring weights for opportunity evaluation."""
    repo = UserPreferencesRepository(db)
    try:
        prefs = repo.update_scoring_weights(
            str(user_id),
            update.skill_gap_weight,
            update.recency_weight,
            update.company_weight,
        )
        db.commit()
        return prefs.to_dict()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.patch("/user/{user_id}/embedding-thresholds", response_model=UserPreferencesResponse)
async def update_embedding_thresholds(
    user_id: UUID,
    update: EmbeddingThresholdsUpdate,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Update embedding filter thresholds for fast/LLM decision."""
    repo = UserPreferencesRepository(db)
    try:
        prefs = repo.update_embedding_thresholds(
            str(user_id),
            update.accept_threshold,
            update.reject_threshold,
        )
        db.commit()
        return prefs.to_dict()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.patch("/user/{user_id}/notifications", response_model=UserPreferencesResponse)
async def update_notification_preferences(
    user_id: UUID,
    update: NotificationPreferencesUpdate,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Update notification delivery channels and thresholds."""
    repo = UserPreferencesRepository(db)
    prefs = repo.update_notification_preferences(
        str(user_id),
        update.channels,
        update.digest_min_score,
        update.instant_alert_min_score,
    )
    db.commit()
    return prefs.to_dict()


@router.patch("/user/{user_id}/display", response_model=UserPreferencesResponse)
async def update_display_preferences(
    user_id: UUID,
    update: DisplayPreferencesUpdate,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Update display, sorting, and pagination preferences."""
    repo = UserPreferencesRepository(db)
    prefs = repo.update_display_preferences(
        str(user_id),
        update.sort_by,
        update.items_per_page,
        update.show_unmatched,
    )
    db.commit()
    return prefs.to_dict()


@router.patch("/user/{user_id}/search", response_model=UserPreferencesResponse)
async def update_search_preferences(
    user_id: UUID,
    update: SearchPreferencesUpdate,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Update job board and search result preferences."""
    repo = UserPreferencesRepository(db)
    prefs = repo.update_search_preferences(
        str(user_id),
        update.preferred_job_boards,
        update.results_per_query,
    )
    db.commit()
    return prefs.to_dict()


@router.patch("/user/{user_id}/llm", response_model=UserPreferencesResponse)
async def update_llm_preferences(
    user_id: UUID,
    update: LLMPreferencesUpdate,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Update LLM backend selection and preferences."""
    repo = UserPreferencesRepository(db)
    prefs = repo.update_llm_preferences(
        str(user_id),
        update.enable_reranking,
        update.provider,
        update.model,
    )
    db.commit()
    return prefs.to_dict()


@router.post("/user/{user_id}/reset-defaults", response_model=UserPreferencesResponse)
async def reset_to_defaults(
    user_id: UUID,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Reset all preferences to system defaults."""
    repo = UserPreferencesRepository(db)
    prefs = repo.reset_to_defaults(str(user_id))
    db.commit()
    return prefs.to_dict()
