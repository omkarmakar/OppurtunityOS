"""Search history endpoints."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.api.deps import get_db
from database.repositories import SearchRepository

router = APIRouter()


class LatestSearchResponse(BaseModel):
    id: UUID
    query: str
    result_count: int = 0
    last_run_at: datetime | None = None
    created_at: datetime


@router.get("/searches/latest", response_model=LatestSearchResponse | None)
def get_latest_search(
    user_id: UUID = Query(description="User ID"),
    db: Session = Depends(get_db),
) -> LatestSearchResponse | None:
    repo = SearchRepository(db)
    searches = repo.list(user_id=user_id)
    if not searches:
        return None
    latest = max(searches, key=lambda s: s.created_at)
    return LatestSearchResponse(
        id=latest.id,
        query=latest.query,
        result_count=latest.result_count,
        last_run_at=latest.last_run_at,
        created_at=latest.created_at,
    )
