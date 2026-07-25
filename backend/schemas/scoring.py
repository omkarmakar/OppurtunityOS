"""Opportunity scoring schemas."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field


class ScoreOpportunityRequest(BaseModel):
    title: str = Field(description="Opportunity title")
    description: str | None = Field(default=None, description="Opportunity description")
    url: str | None = Field(default=None, description="Opportunity URL")
    provider: str | None = Field(default=None, description="AI provider override")
    model: str | None = Field(default=None, description="Model override")


class ScoreAndSaveRequest(BaseModel):
    opportunity_ids: list[UUID] = Field(description="Opportunity IDs to score")
    provider: str | None = Field(default=None, description="AI provider override")
    model: str | None = Field(default=None, description="Model override")


class ScoredOpportunityResponse(BaseModel):
    opportunity_id: str = ""
    title: str = ""
    url: str = ""
    relevance_score: float = 0.0
    summary: str = ""
    pros: list[str] = []
    cons: list[str] = []
    required_skills: list[str] = []
    missing_skills: list[str] = []
    application_deadline: str = ""
    ranking_explanation: str = ""


class BatchScoreResponse(BaseModel):
    results: list[ScoredOpportunityResponse] = []
