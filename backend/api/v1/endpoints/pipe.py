"""Search pipeline trigger endpoint."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.api.deps import get_db
from database.repositories.profile_repository import ProfileRepository
from services.search_pipeline import PipelineConfig, PipelineResult, SearchPipeline

router = APIRouter()


class PipelineResponse(BaseModel):
    success: bool
    queries_generated: list[str] = []
    search_results_count: int = 0
    pages_extracted: int = 0
    opportunities_created: int = 0
    opportunities_skipped_duplicate: int = 0
    opportunities_scored: int = 0
    notifications_sent: int = 0
    error: str = ""


@router.post("/pipeline/run", response_model=PipelineResponse)
async def run_pipeline(
    profile_id: UUID = Query(description="Profile ID to run pipeline for"),
    search_provider: str = Query(default="tavily", description="Search provider name"),
    max_queries: int = Query(default=5, ge=1, le=20, description="Max search queries"),
    max_results: int = Query(default=10, ge=1, le=50, description="Max results per query"),
    skip_ranking: bool = Query(default=False, description="Skip AI ranking step"),
    db: Session = Depends(get_db),
) -> PipelineResponse:
    profile_repo = ProfileRepository(db)
    profile = profile_repo.get(profile_id)
    if not profile:
        raise HTTPException(
            status_code=404,
            detail=f"Profile with id '{profile_id}' not found",
        )

    config = PipelineConfig(
        query_count=max_queries,
        search_provider=search_provider,
        search_result_count=max_results,
        ai_ranking_enabled=not skip_ranking,
    )

    pipeline = SearchPipeline(db=db, config=config)
    result: PipelineResult = await pipeline.run(profile)

    if result.success:
        db.commit()

    return PipelineResponse(
        success=result.success,
        queries_generated=result.queries_generated,
        search_results_count=result.search_results_count,
        pages_extracted=result.pages_extracted,
        opportunities_created=result.opportunities_created,
        opportunities_skipped_duplicate=result.opportunities_skipped_duplicate,
        opportunities_scored=result.opportunities_scored,
        notifications_sent=result.notifications_sent,
        error=result.error,
    )