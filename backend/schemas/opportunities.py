"""Opportunity response schemas."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class OpportunityDetailResponse(BaseModel):
    id: UUID
    user_id: UUID
    source_id: UUID | None = None
    title: str
    description: str | None = None
    url: str | None = None
    source_type: str | None = None
    status: str
    priority: str
    relevance_score: float | None = None
    summary: str | None = None
    pros: list[str] | None = None
    cons: list[str] | None = None
    required_skills: list[str] | None = None
    missing_skills: list[str] | None = None
    application_deadline: str | None = None
    ranking_explanation: str | None = None
    ai_scored_at: datetime | None = None
    last_seen_at: datetime | None = None
    discovered_at: datetime
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class OpportunityListResponse(BaseModel):
    items: list[OpportunityDetailResponse]
    total: int
    page: int
    page_size: int


class UpdateStatusRequest(BaseModel):
    status: str = Field(..., description="New status value")
