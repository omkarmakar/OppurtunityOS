"""Bookmark response schemas."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class BookmarkDetailResponse(BaseModel):
    id: UUID
    user_id: UUID
    opportunity_id: UUID
    opportunity_title: str = ""
    opportunity_url: str | None = None
    relevance_score: float | None = None
    notes: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class BookmarkListResponse(BaseModel):
    items: list[BookmarkDetailResponse]
    total: int
    page: int
    page_size: int


class CreateBookmarkRequest(BaseModel):
    user_id: UUID
    opportunity_id: UUID
    notes: str | None = None


class UpdateBookmarkNotesRequest(BaseModel):
    notes: str | None = None


class CreateBookmarkResponse(BaseModel):
    id: UUID
    user_id: UUID
    opportunity_id: UUID
    notes: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
