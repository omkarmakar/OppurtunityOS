"""User account schemas."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class UserResponse(BaseModel):
    id: UUID
    email: str
    is_active: bool
    is_verified: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class UserUpsert(BaseModel):
    """Body for PUT /users/{user_id} — all fields optional.

    The endpoint performs an upsert: it creates the User row if it doesn't
    exist yet, or updates only the supplied fields if it does.
    """

    email: str | None = Field(
        default=None,
        description="Email address used for digest delivery and notifications.",
    )
    is_active: bool | None = Field(default=None)

    @field_validator("email")
    @classmethod
    def _validate_email(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.strip()
        if v and "@" not in v:
            raise ValueError("value is not a valid email address")
        return v
