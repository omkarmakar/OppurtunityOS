"""Search pipeline trigger endpoint."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.api.deps import get_db
from database.models.profiles import Profile
from database.repositories.profile_repository import ProfileRepository
from database.repositories.user_repository import UserRepository
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
    user_id: UUID = Query(description="User ID to run pipeline for"),
    search_provider: str = Query(default="dummy", description="Search provider name"),
    max_queries: int = Query(default=5, ge=1, le=20, description="Max search queries"),
    max_results: int = Query(default=10, ge=1, le=50, description="Max results per query"),
    skip_ranking: bool = Query(default=False, description="Skip AI ranking step"),
    db: Session = Depends(get_db),
) -> PipelineResponse:
    profile_repo = ProfileRepository(db)
    profile = profile_repo.get_by_user_id(user_id)
    if not profile:
        # Auto-create a default profile for the user if none exists yet
        # so the search pipeline can run without requiring prior setup.
        user_repo = UserRepository(db)
        user_repo.get_or_create(user_id)
        profile = Profile(
            user_id=user_id,
            display_name="Default Profile",
            skills=["Software Engineer", "Python", "Developer"],
            keywords=["developer", "python", "software", "remote"],
        )
        profile_repo.add(profile)
        db.commit()
        db.refresh(profile)

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
