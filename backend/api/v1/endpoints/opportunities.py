"""Opportunity endpoints — list, filter, detail, and status updates."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func as sa_func
from sqlalchemy.orm import Session

from backend.api.deps import get_db
from backend.schemas.opportunities import (
    OpportunityDetailResponse,
    OpportunityListResponse,
    UpdateStatusRequest,
)
from database.models.opportunities import Opportunity
from database.repositories.opportunity_repository import OpportunityRepository

router = APIRouter()

VALID_STATUSES = frozenset({"new", "reviewed", "applied", "interview", "rejected", "accepted"})


@router.get("/opportunities", response_model=OpportunityListResponse)
def list_opportunities(
    user_id: UUID = Query(..., description="User ID"),
    status_filter: str | None = Query(None, alias="status", description="Filter by status"),
    min_score: float | None = Query(None, ge=0, le=100, description="Minimum relevance score"),
    sort_by: str = Query("score", pattern="^(score|date)$"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    db: Session = Depends(get_db),
) -> OpportunityListResponse:
    query = db.query(Opportunity).filter(Opportunity.user_id == user_id)

    if status_filter:
        query = query.filter(Opportunity.status == status_filter)

    if min_score is not None:
        query = query.filter(Opportunity.relevance_score >= min_score)

    total = query.count()

    if sort_by == "score":
        query = query.order_by(Opportunity.relevance_score.desc().nullslast(), Opportunity.created_at.desc())
    else:
        query = query.order_by(Opportunity.created_at.desc())

    offset = (page - 1) * page_size
    items = query.offset(offset).limit(page_size).all()

    return OpportunityListResponse(
        items=[OpportunityDetailResponse.model_validate(o) for o in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/opportunities/{opportunity_id}", response_model=OpportunityDetailResponse)
def get_opportunity(
    opportunity_id: UUID,
    db: Session = Depends(get_db),
) -> OpportunityDetailResponse:
    opp = db.get(Opportunity, opportunity_id)
    if not opp:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Opportunity not found")
    return OpportunityDetailResponse.model_validate(opp)


@router.patch("/opportunities/{opportunity_id}/status", response_model=OpportunityDetailResponse)
def update_opportunity_status(
    opportunity_id: UUID,
    body: UpdateStatusRequest,
    db: Session = Depends(get_db),
) -> OpportunityDetailResponse:
    if body.status not in VALID_STATUSES:
        valid = ", ".join(sorted(VALID_STATUSES))
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid status '{body.status}'. Must be one of: {valid}",
        )

    repo = OpportunityRepository(db)
    opp = repo.get(opportunity_id)
    if not opp:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Opportunity not found")

    opp.status = body.status
    repo.update(opp)
    db.commit()
    db.refresh(opp)
    return OpportunityDetailResponse.model_validate(opp)
