"""Opportunity model."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Index, Integer, String, Text, Uuid, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base

if TYPE_CHECKING:
    from database.models.bookmarks import Bookmark
    from database.models.profiles import Profile
    from database.models.sources import Source
    from database.models.users import User


class Opportunity(Base):
    __tablename__ = "opportunities"

    __table_args__ = (
        Index(
            "ix_opportunities_user_url",
            "user_id",
            "url",
            unique=True,
            sqlite_where=text("url IS NOT NULL AND url != ''"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    profile_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True, index=True,
    )
    source_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("sources.id", ondelete="SET NULL"), nullable=True,
    )
    title: Mapped[str] = mapped_column(
        String(500), nullable=False,
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True,
    )
    url: Mapped[Optional[str]] = mapped_column(
        String(2000), nullable=True,
    )
    source_type: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True,
    )
    company: Mapped[Optional[str]] = mapped_column(
        String(500), nullable=True,
    )
    industry: Mapped[Optional[str]] = mapped_column(
        String(200), nullable=True,
    )
    status: Mapped[str] = mapped_column(
        String(50), default="new", nullable=False, index=True,
    )
    priority: Mapped[str] = mapped_column(
        String(20), default="medium", nullable=False,
    )
    metadata_: Mapped[Optional[dict[str, Any]]] = mapped_column(
        "metadata", JSON, nullable=True,
    )
    posted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    deadline_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    application_deadline_raw: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True,
    )
    discovered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
    )

    # ── AI scoring fields ────────────────────────────────────────────
    relevance_score: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True,
    )
    summary: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True,
    )
    pros: Mapped[Optional[list[str]]] = mapped_column(
        JSON, nullable=True,
    )
    cons: Mapped[Optional[list[str]]] = mapped_column(
        JSON, nullable=True,
    )
    required_skills: Mapped[Optional[list[str]]] = mapped_column(
        JSON, nullable=True,
    )
    missing_skills: Mapped[Optional[list[str]]] = mapped_column(
        JSON, nullable=True,
    )
    ranking_explanation: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True,
    )
    # Deprecated: use deadline_at instead. Kept for backward compatibility during migration.
    application_deadline: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True,
    )
    ai_scored_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )

    last_seen_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False,
    )

    user: Mapped[User] = relationship(
        "User", back_populates="opportunities",
    )
    source: Mapped[Optional[Source]] = relationship(
        "Source", back_populates="opportunities",
    )
    bookmarks: Mapped[list[Bookmark]] = relationship(
        "Bookmark", back_populates="opportunity", cascade="all, delete-orphan",
    )
