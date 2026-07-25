"""Profile CRUD endpoints."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.api.deps import get_db
from backend.schemas.profiles import ProfileCreate, ProfileResponse, ProfileUpdate
from database.models import Profile
from database.repositories import ProfileRepository

router = APIRouter()


@router.get("/profiles/{user_id}", response_model=ProfileResponse)
def get_profile(user_id: UUID, db: Session = Depends(get_db)) -> ProfileResponse:
    repo = ProfileRepository(db)
    profile = repo.get_by_user_id(user_id)
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")
    return ProfileResponse.model_validate(profile)


@router.post("/profiles", response_model=ProfileResponse, status_code=status.HTTP_201_CREATED)
def create_profile(data: ProfileCreate, db: Session = Depends(get_db)) -> ProfileResponse:
    repo = ProfileRepository(db)
    existing = repo.get_by_user_id(data.user_id)
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Profile already exists")
    profile = Profile(**data.model_dump())
    repo.add(profile)
    db.commit()
    db.refresh(profile)
    return ProfileResponse.model_validate(profile)


@router.put("/profiles/{user_id}", response_model=ProfileResponse)
def update_profile(
    user_id: UUID, data: ProfileUpdate, db: Session = Depends(get_db),
) -> ProfileResponse:
    repo = ProfileRepository(db)
    profile = repo.get_by_user_id(user_id)
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(profile, key, value)
    repo.update(profile)
    db.commit()
    db.refresh(profile)
    return ProfileResponse.model_validate(profile)


@router.delete("/profiles/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_profile(user_id: UUID, db: Session = Depends(get_db)) -> None:
    repo = ProfileRepository(db)
    profile = repo.get_by_user_id(user_id)
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")
    repo.delete(profile)
    db.commit()
