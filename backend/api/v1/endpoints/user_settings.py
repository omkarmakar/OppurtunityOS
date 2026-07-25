"""User-level settings endpoints — preferences per user, not global config."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.api.deps import get_db
from backend.schemas.user_settings import (
    UpdateUserSettingsRequest,
    UserSettingsResponse,
)
from database.models.profiles import Profile
from database.repositories import ApplicationSettingsRepository

router = APIRouter()


def _ensure_user_exists(user_id: UUID, db: Session) -> None:
    """Return 404 if the user (via profile) does not exist."""
    exists = db.query(Profile.id).filter(Profile.user_id == user_id).first() is not None
    if not exists:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found — create a profile first",
        )


@router.get("/user-settings", response_model=UserSettingsResponse)
def get_user_settings(
    user_id: UUID = Query(description="User ID"),
    db: Session = Depends(get_db),
) -> UserSettingsResponse:
    _ensure_user_exists(user_id, db)
    repo = ApplicationSettingsRepository(db)
    settings = repo.get_by_user_id(user_id)
    if not settings:
        settings = repo.upsert(user_id)
        db.commit()
        db.refresh(settings)
    return UserSettingsResponse.model_validate(settings)


@router.put("/user-settings", response_model=UserSettingsResponse)
def update_user_settings(
    user_id: UUID = Query(description="User ID"),
    body: UpdateUserSettingsRequest = None,
    db: Session = Depends(get_db),
) -> UserSettingsResponse:
    _ensure_user_exists(user_id, db)
    repo = ApplicationSettingsRepository(db)
    update_data = body.model_dump(exclude_unset=True) if body else {}
    settings = repo.upsert(user_id, **update_data)
    db.commit()
    db.refresh(settings)
    return UserSettingsResponse.model_validate(settings)
