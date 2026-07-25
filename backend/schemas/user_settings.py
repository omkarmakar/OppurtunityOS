"""User settings request/response schemas."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class UserSettingsResponse(BaseModel):
    theme: str = "system"
    language: str = "en"
    notifications_enabled: bool = True
    notification_preferences: dict | None = None
    default_search_provider: str = "dummy"
    default_max_queries: int = 5
    default_max_results: int = 10
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class UpdateUserSettingsRequest(BaseModel):
    theme: str | None = None
    language: str | None = None
    notifications_enabled: bool | None = None
    notification_preferences: dict | None = None
    default_search_provider: str | None = None
    default_max_queries: int | None = Field(default=None, ge=1, le=20)
    default_max_results: int | None = Field(default=None, ge=1, le=50)
