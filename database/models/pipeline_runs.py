"""Pipeline run model — persists search pipeline execution history."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base

if TYPE_CHECKING:
    from database.models.users import User


class PipelineRun(Base):
    __tablename__ = "pipeline_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
    )
    finished_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    success: Mapped[Optional[bool]] = mapped_column(
        Boolean, nullable=True,
    )
    queries_generated: Mapped[Optional[list[str]]] = mapped_column(
        JSON, nullable=True,
    )
    search_results_count: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False,
    )
    opportunities_created: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False,
    )
    opportunities_skipped_duplicate: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False,
    )
    opportunities_scored: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False,
    )
    error: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True,
    )
    step_results: Mapped[Optional[dict[str, Any]]] = mapped_column(
        JSON, nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False,
    )

    user: Mapped[User] = relationship(
        "User", back_populates="pipeline_runs",
    )
