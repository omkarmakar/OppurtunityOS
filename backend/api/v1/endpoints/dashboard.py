"""Dashboard data endpoint."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func as sa_func
from sqlalchemy.orm import Session, joinedload

from backend.api.deps import get_db
from backend.schemas.dashboard import (
    DailyTrend,
    DashboardOpportunity,
    DashboardResponse,
    DashboardSearch,
    DashboardStats,
    ScoreDistribution,
    StatusBreakdown,
    TopBookmark,
)
from database.models import Bookmark, Notification, Opportunity, Search as SearchModel
from services.cache import QueryCache

router = APIRouter()
_dashboard_cache = QueryCache(ttl=15.0, max_size=100)


@router.get("/dashboard", response_model=DashboardResponse)
def get_dashboard(
    user_id: UUID = Query(description="User ID"),
    db: Session = Depends(get_db),
) -> DashboardResponse:
    cached = _dashboard_cache.get(str(user_id))
    if cached is not None:
        return cached
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    total_opps: int = db.query(sa_func.count(Opportunity.id)).filter(
        Opportunity.user_id == user_id,
    ).scalar() or 0

    total_searches: int = db.query(sa_func.count(SearchModel.id)).filter(
        SearchModel.user_id == user_id,
    ).scalar() or 0

    total_bookmarks: int = db.query(sa_func.count(Bookmark.id)).filter(
        Bookmark.user_id == user_id,
    ).scalar() or 0

    unread_notifs: int = db.query(sa_func.count(Notification.id)).filter(
        Notification.user_id == user_id,
        Notification.is_read == False,
    ).scalar() or 0

    today_searches: int = db.query(sa_func.count(SearchModel.id)).filter(
        SearchModel.user_id == user_id,
        SearchModel.created_at >= today_start,
    ).scalar() or 0

    avg_score: float = db.query(sa_func.avg(Opportunity.relevance_score)).filter(
        Opportunity.user_id == user_id,
        Opportunity.relevance_score.isnot(None),
    ).scalar() or 0.0

    stats = DashboardStats(
        total_opportunities=total_opps,
        total_searches=total_searches,
        total_bookmarks=total_bookmarks,
        unread_notifications=unread_notifs,
        today_searches=today_searches,
        avg_relevance_score=round(float(avg_score), 1),
    )

    top_opps = (
        db.query(Opportunity)
        .filter(Opportunity.user_id == user_id, Opportunity.relevance_score.isnot(None))
        .order_by(Opportunity.relevance_score.desc())
        .limit(10)
        .all()
    )

    bookmarked_opp_ids = {
        row[0]
        for row in db.query(Bookmark.opportunity_id).filter(Bookmark.user_id == user_id).all()
    }

    top_opportunities = [
        DashboardOpportunity(
            id=o.id,
            title=o.title,
            url=o.url,
            status=o.status,
            priority=o.priority,
            relevance_score=o.relevance_score,
            summary=o.summary,
            application_deadline=o.application_deadline,
            created_at=o.created_at,
            is_bookmarked=o.id in bookmarked_opp_ids,
        )
        for o in top_opps
    ]

    recent_searches = (
        db.query(SearchModel)
        .filter(SearchModel.user_id == user_id)
        .order_by(SearchModel.created_at.desc())
        .limit(10)
        .all()
    )

    searches = [
        DashboardSearch(
            id=s.id,
            query=s.query,
            result_count=s.result_count,
            last_run_at=s.last_run_at,
            created_at=s.created_at,
        )
        for s in recent_searches
    ]

    upcoming = (
        db.query(Opportunity)
        .filter(
            Opportunity.user_id == user_id,
            Opportunity.application_deadline.isnot(None),
            Opportunity.application_deadline != "",
        )
        .order_by(Opportunity.application_deadline.asc())
        .limit(10)
        .all()
    )

    deadlines = [
        DashboardOpportunity(
            id=o.id,
            title=o.title,
            url=o.url,
            status=o.status,
            priority=o.priority,
            relevance_score=o.relevance_score,
            summary=o.summary,
            application_deadline=o.application_deadline,
            created_at=o.created_at,
            is_bookmarked=o.id in bookmarked_opp_ids,
        )
        for o in upcoming
    ]

    bookmark_rows = (
        db.query(Bookmark)
        .options(joinedload(Bookmark.opportunity))
        .filter(Bookmark.user_id == user_id)
        .order_by(Bookmark.created_at.desc())
        .limit(10)
        .all()
    )

    bookmarks = [
        TopBookmark(
            opportunity_id=b.opportunity_id,
            opportunity_title=b.opportunity.title if b.opportunity else "Untitled",
            opportunity_url=b.opportunity.url if b.opportunity else None,
            notes=b.notes,
            created_at=b.created_at,
        )
        for b in bookmark_rows
        if b.opportunity
    ]

    score_dist = _build_score_distribution(db, user_id)
    status_break = _build_status_breakdown(db, user_id)
    daily = _build_daily_trend(db, user_id, now)

    response = DashboardResponse(
        stats=stats,
        top_opportunities=top_opportunities,
        recent_searches=searches,
        upcoming_deadlines=deadlines,
        bookmarks=bookmarks,
        score_distribution=score_dist,
        status_breakdown=status_break,
        daily_trend=daily,
    )
    _dashboard_cache.set(str(user_id), response)
    return response


def _build_score_distribution(db: Session, user_id: UUID) -> list[ScoreDistribution]:
    bins = [
        (0, 20), (20, 40), (40, 60), (60, 80), (80, 100),
    ]
    result: list[ScoreDistribution] = []
    for start, end in bins:
        count = (
            db.query(sa_func.count(Opportunity.id))
            .filter(
                Opportunity.user_id == user_id,
                Opportunity.relevance_score >= start,
                Opportunity.relevance_score < end,
            )
            .scalar() or 0
        )
        result.append(ScoreDistribution(range_start=start, range_end=end, count=count))
    return result


def _build_status_breakdown(db: Session, user_id: UUID) -> list[StatusBreakdown]:
    rows = (
        db.query(Opportunity.status, sa_func.count(Opportunity.id))
        .filter(Opportunity.user_id == user_id)
        .group_by(Opportunity.status)
        .all()
    )
    return [StatusBreakdown(status=row[0], count=row[1]) for row in rows]


def _build_daily_trend(db: Session, user_id: UUID, now: datetime) -> list[DailyTrend]:
    days = 14
    rows = (
        db.query(
            sa_func.date(Opportunity.created_at),
            sa_func.count(Opportunity.id),
        )
        .filter(
            Opportunity.user_id == user_id,
            Opportunity.created_at >= now - timedelta(days=days),
        )
        .group_by(sa_func.date(Opportunity.created_at))
        .all()
    )
    date_map = {str(row[0]): row[1] for row in rows}
    trend: list[DailyTrend] = []
    for i in range(days - 1, -1, -1):
        d = (now - timedelta(days=i)).strftime("%Y-%m-%d")
        trend.append(DailyTrend(date=d, count=date_map.get(d, 0)))
    return trend
