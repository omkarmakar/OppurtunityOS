"""Dashboard response schemas."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class DashboardStats(BaseModel):
    total_opportunities: int = 0
    total_searches: int = 0
    total_bookmarks: int = 0
    unread_notifications: int = 0
    today_searches: int = 0
    avg_relevance_score: float = 0.0


class DashboardOpportunity(BaseModel):
    id: UUID
    title: str
    url: str | None = None
    status: str = ""
    priority: str = ""
    relevance_score: float | None = None
    summary: str | None = None
    application_deadline: str | None = None
    created_at: datetime
    is_bookmarked: bool = False


class DashboardSearch(BaseModel):
    id: UUID
    query: str
    result_count: int = 0
    last_run_at: datetime | None = None
    created_at: datetime


class TopBookmark(BaseModel):
    opportunity_id: UUID
    opportunity_title: str
    opportunity_url: str | None = None
    notes: str | None = None
    created_at: datetime


class ScoreDistribution(BaseModel):
    range_start: int = 0
    range_end: int = 100
    count: int = 0


class StatusBreakdown(BaseModel):
    status: str = ""
    count: int = 0


class DailyTrend(BaseModel):
    date: str = ""
    count: int = 0


class DashboardResponse(BaseModel):
    stats: DashboardStats = Field(default_factory=DashboardStats)
    top_opportunities: list[DashboardOpportunity] = []
    recent_searches: list[DashboardSearch] = []
    upcoming_deadlines: list[DashboardOpportunity] = []
    bookmarks: list[TopBookmark] = []
    score_distribution: list[ScoreDistribution] = []
    status_breakdown: list[StatusBreakdown] = []
    daily_trend: list[DailyTrend] = []
