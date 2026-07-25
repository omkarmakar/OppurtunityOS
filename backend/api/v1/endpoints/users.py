"""User account endpoints.

Provides the minimal surface needed to claim a user_id with a real email
address (required for digest delivery) and to inspect the current user row.

Routes
------
GET  /users/{user_id}       — fetch an existing user (404 if absent)
PUT  /users/{user_id}       — upsert: create the row if missing, then apply
                              any supplied fields.  Idempotent — safe to call
                              on every app start to ensure the row exists.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.api.deps import get_db
from backend.schemas.users import UserResponse, UserUpsert
from database.repositories import UserRepository

router = APIRouter()


@router.get("/users/{user_id}", response_model=UserResponse)
def get_user(user_id: UUID, db: Session = Depends(get_db)) -> UserResponse:
    """Return the User row for *user_id*.

    Raises 404 when no row exists — use PUT to create one.
    """
    repo = UserRepository(db)
    user = repo.get(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    return UserResponse.model_validate(user)


@router.put("/users/{user_id}", response_model=UserResponse)
def upsert_user(
    user_id: UUID,
    data: UserUpsert,
    db: Session = Depends(get_db),
) -> UserResponse:
    """Create or update the User row for *user_id*.

    - If the row does not exist it is created with the supplied email
      (or a placeholder if none provided).
    - If the row already exists only the non-None fields in the request
      body are applied; unset fields are left unchanged.

    This is the primary way for the frontend to store a real email address
    so that digest delivery works.
    """
    repo = UserRepository(db)

    email_str = data.email if data.email else ""
    user = repo.get_or_create(user_id, email=email_str)

    # Apply any explicitly supplied updates on top of the created/fetched row.
    if data.email is not None:
        user.email = data.email
    if data.is_active is not None:
        user.is_active = data.is_active

    repo.update(user)
    db.commit()
    db.refresh(user)
    return UserResponse.model_validate(user)
