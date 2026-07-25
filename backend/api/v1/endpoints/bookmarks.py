"""Bookmark endpoints — create, delete, and list."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func as sa_func
from sqlalchemy.orm import Session, joinedload

from backend.api.deps import get_db
from backend.schemas.bookmarks import (
    BookmarkDetailResponse,
    BookmarkListResponse,
    CreateBookmarkRequest,
    CreateBookmarkResponse,
    UpdateBookmarkNotesRequest,
)
from database.models.bookmarks import Bookmark
from database.models.opportunities import Opportunity
from database.repositories.bookmark_repository import BookmarkRepository

router = APIRouter()


@router.post("/bookmarks", response_model=CreateBookmarkResponse, status_code=status.HTTP_201_CREATED)
def create_bookmark(
    body: CreateBookmarkRequest,
    db: Session = Depends(get_db),
) -> CreateBookmarkResponse:
    # Check for duplicate
    existing = (
        db.query(Bookmark)
        .filter(
            Bookmark.user_id == body.user_id,
            Bookmark.opportunity_id == body.opportunity_id,
        )
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Bookmark already exists for this user and opportunity",
        )

    # Verify opportunity exists
    opp = db.get(Opportunity, body.opportunity_id)
    if not opp:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Opportunity not found",
        )

    bookmark = Bookmark(
        user_id=body.user_id,
        opportunity_id=body.opportunity_id,
        notes=body.notes,
    )
    repo = BookmarkRepository(db)
    repo.add(bookmark)
    db.commit()
    db.refresh(bookmark)
    return CreateBookmarkResponse.model_validate(bookmark)


@router.patch("/bookmarks/{bookmark_id}", response_model=BookmarkDetailResponse)
def update_bookmark_notes(
    bookmark_id: UUID,
    body: UpdateBookmarkNotesRequest,
    db: Session = Depends(get_db),
) -> BookmarkDetailResponse:
    repo = BookmarkRepository(db)
    bookmark = repo.get(bookmark_id)
    if not bookmark:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bookmark not found")
    if body.notes is not None:
        bookmark.notes = body.notes
    repo.update(bookmark)
    db.commit()
    db.refresh(bookmark)
    return BookmarkDetailResponse(
        id=bookmark.id,
        user_id=bookmark.user_id,
        opportunity_id=bookmark.opportunity_id,
        opportunity_title=bookmark.opportunity.title if bookmark.opportunity else "Untitled",
        opportunity_url=bookmark.opportunity.url if bookmark.opportunity else None,
        relevance_score=bookmark.opportunity.relevance_score if bookmark.opportunity else None,
        notes=bookmark.notes,
        created_at=bookmark.created_at,
    )


@router.delete("/bookmarks/{bookmark_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_bookmark(
    bookmark_id: UUID,
    db: Session = Depends(get_db),
) -> None:
    repo = BookmarkRepository(db)
    bookmark = repo.get(bookmark_id)
    if not bookmark:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bookmark not found")
    repo.delete(bookmark)
    db.commit()


@router.get("/bookmarks", response_model=BookmarkListResponse)
def list_bookmarks(
    user_id: UUID = Query(..., description="User ID"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    db: Session = Depends(get_db),
) -> BookmarkListResponse:
    total = (
        db.query(sa_func.count(Bookmark.id))
        .filter(Bookmark.user_id == user_id)
        .scalar() or 0
    )

    offset = (page - 1) * page_size
    rows = (
        db.query(Bookmark)
        .options(joinedload(Bookmark.opportunity))
        .filter(Bookmark.user_id == user_id)
        .order_by(Bookmark.created_at.desc())
        .offset(offset)
        .limit(page_size)
        .all()
    )

    items = [
        BookmarkDetailResponse(
            id=b.id,
            user_id=b.user_id,
            opportunity_id=b.opportunity_id,
            opportunity_title=b.opportunity.title if b.opportunity else "Untitled",
            opportunity_url=b.opportunity.url if b.opportunity else None,
            relevance_score=b.opportunity.relevance_score if b.opportunity else None,
            notes=b.notes,
            created_at=b.created_at,
        )
        for b in rows
        if b.opportunity
    ]

    return BookmarkListResponse(items=items, total=total, page=page, page_size=page_size)
