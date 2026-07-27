"""Profile CRUD endpoints — multi-profile support.

A user can have up to 5 profiles (e.g. different resume framings for
different job tracks).  All new endpoints key off ``profile_id`` (UUID)
for single-profile operations.  The old ``/profiles/{user_id}`` routes
are kept for backward compatibility but are deprecated.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.api.deps import get_db
from backend.schemas.profiles import ProfileCreate, ProfileResponse, ProfileUpdate
from core.config.settings import AppConfig
from database.models import Profile
from database.repositories import ProfileRepository, UserRepository

router = APIRouter()


def _get_max_slots() -> int:
    return AppConfig().profiles.max_slots_per_user


# ── Listing endpoint (user_id-based) ──────────────────────────────────


@router.get("/users/{user_id}/profiles", response_model=list[ProfileResponse])
def list_profiles(user_id: UUID, db: Session = Depends(get_db)) -> list[ProfileResponse]:
    """List all profiles for a user (max N, no pagination needed)."""
    repo = ProfileRepository(db)
    profiles = repo.list_by_user_id(user_id)
    return [ProfileResponse.model_validate(p) for p in profiles]


# ── Create ────────────────────────────────────────────────────────────


@router.post("/profiles", response_model=ProfileResponse, status_code=status.HTTP_201_CREATED)
def create_profile(data: ProfileCreate, db: Session = Depends(get_db)) -> ProfileResponse:
    """Create a new profile for a user (max N per user)."""
    repo = ProfileRepository(db)
    max_slots = _get_max_slots()

    # Enforce the cap
    count = repo.count_by_user_id(data.user_id)
    if count >= max_slots:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Maximum of {max_slots} profiles per user reached",
        )

    # Ensure a User row exists before creating the Profile so the FK is
    # satisfied on all databases, including Postgres where it is enforced.
    UserRepository(db).get_or_create(data.user_id)
    profile = Profile(**data.model_dump())
    repo.add(profile)
    db.commit()
    db.refresh(profile)
    return ProfileResponse.model_validate(profile)


# ── Profile-ID-based CRUD (new, preferred) ────────────────────────────


@router.get("/profiles/id/{profile_id}", response_model=ProfileResponse)
def get_profile(profile_id: UUID, db: Session = Depends(get_db)) -> ProfileResponse:
    """Fetch a single profile by its own id (not user_id)."""
    repo = ProfileRepository(db)
    profile = repo.get(profile_id)
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")
    return ProfileResponse.model_validate(profile)


@router.put("/profiles/id/{profile_id}", response_model=ProfileResponse)
def update_profile(
    profile_id: UUID, data: ProfileUpdate, db: Session = Depends(get_db),
) -> ProfileResponse:
    """Update a profile by its id."""
    repo = ProfileRepository(db)
    profile = repo.get(profile_id)
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(profile, key, value)
    repo.update(profile)
    db.commit()
    db.refresh(profile)
    return ProfileResponse.model_validate(profile)


@router.delete("/profiles/id/{profile_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_profile(profile_id: UUID, db: Session = Depends(get_db)) -> None:
    """Delete a profile by its id.

    Does not allow deleting a user's last remaining profile.
    """
    repo = ProfileRepository(db)
    profile = repo.get(profile_id)
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")

    # Don't allow deleting the last profile
    count = repo.count_by_user_id(profile.user_id)
    if count <= 1:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot delete the last remaining profile",
        )

    repo.delete(profile)
    db.commit()


# ── Deprecated user_id-based endpoints (backward compatibility) ───────


@router.get(
    "/profiles/{user_id}",
    response_model=ProfileResponse,
    deprecated=True,
    description="Deprecated: use GET /profiles/id/{profile_id} or GET /users/{user_id}/profiles",
)
def get_profile_by_user_id(user_id: UUID, db: Session = Depends(get_db)) -> ProfileResponse:
    """Deprecated — returns the user's first/oldest profile."""
    repo = ProfileRepository(db)
    profile = repo.get_by_user_id(user_id)
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")
    return ProfileResponse.model_validate(profile)


@router.put(
    "/profiles/{user_id}",
    response_model=ProfileResponse,
    deprecated=True,
    description="Deprecated: use PUT /profiles/id/{profile_id}",
)
def update_profile_by_user_id(
    user_id: UUID, data: ProfileUpdate, db: Session = Depends(get_db),
) -> ProfileResponse:
    """Deprecated — updates the user's first/oldest profile."""
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


@router.delete(
    "/profiles/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    deprecated=True,
    description="Deprecated: use DELETE /profiles/id/{profile_id}",
)
def delete_profile_by_user_id(user_id: UUID, db: Session = Depends(get_db)) -> None:
    """Deprecated — deletes the user's first/oldest profile."""
    repo = ProfileRepository(db)
    profile = repo.get_by_user_id(user_id)
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")

    count = repo.count_by_user_id(user_id)
    if count <= 1:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot delete the last remaining profile",
        )

    repo.delete(profile)
    db.commit()