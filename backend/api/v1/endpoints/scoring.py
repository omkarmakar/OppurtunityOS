"""Opportunity scoring endpoints."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.api.deps import get_db
from backend.schemas.scoring import (
    BatchScoreResponse,
    ScoreAndSaveRequest,
    ScoreOpportunityRequest,
    ScoredOpportunityResponse,
)
from database.models.opportunities import Opportunity
from database.repositories.opportunity_repository import OpportunityRepository
from database.repositories.profile_repository import ProfileRepository
from services.opportunity_scorer import create_opportunity_scorer

router = APIRouter()


@router.post("/opportunities/score", response_model=ScoredOpportunityResponse)
async def score_opportunity(
    req: ScoreOpportunityRequest,
    user_id: UUID = Query(description="User ID whose profile to score against"),
    db: Session = Depends(get_db),
) -> ScoredOpportunityResponse:
    profile_repo = ProfileRepository(db)
    profile = profile_repo.get_by_user_id(user_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    scorer = create_opportunity_scorer(
        provider_name=req.provider,
        model_name=req.model,
    )

    result = await scorer.score_opportunity(
        profile=profile,
        title=req.title,
        description=req.description,
        url=req.url,
    )

    return ScoredOpportunityResponse(
        opportunity_id=result.opportunity_id,
        title=result.title,
        url=result.url,
        relevance_score=result.relevance_score,
        summary=result.summary,
        pros=result.pros,
        cons=result.cons,
        required_skills=result.required_skills,
        missing_skills=result.missing_skills,
        application_deadline=result.application_deadline,
        ranking_explanation=result.ranking_explanation,
    )


@router.post("/opportunities/score-and-save", response_model=BatchScoreResponse)
async def score_and_save_opportunities(
    req: ScoreAndSaveRequest,
    user_id: UUID = Query(description="User ID whose profile to score against"),
    db: Session = Depends(get_db),
) -> BatchScoreResponse:
    profile_repo = ProfileRepository(db)
    profile = profile_repo.get_by_user_id(user_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    opp_repo = OpportunityRepository(db)
    opportunities: list[Opportunity] = []
    for oid in req.opportunity_ids:
        opp = opp_repo.get(oid)
        if opp is None:
            raise HTTPException(
                status_code=404, detail=f"Opportunity not found: {oid}"
            )
        opportunities.append(opp)

    scorer = create_opportunity_scorer(
        provider_name=req.provider,
        model_name=req.model,
    )

    results = await scorer.score_multiple_and_save(profile, opportunities)
    db.flush()

    return BatchScoreResponse(
        results=[
            ScoredOpportunityResponse(
                opportunity_id=r.opportunity_id,
                title=r.title,
                url=r.url,
                relevance_score=r.relevance_score,
                summary=r.summary,
                pros=r.pros,
                cons=r.cons,
                required_skills=r.required_skills,
                missing_skills=r.missing_skills,
                application_deadline=r.application_deadline,
                ranking_explanation=r.ranking_explanation,
            )
            for r in results
        ],
    )
