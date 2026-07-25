"""User account model."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Boolean, DateTime, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base

if TYPE_CHECKING:
    from database.models.application_settings import ApplicationSettings
    from database.models.bookmarks import Bookmark
    from database.models.notifications import Notification
    from database.models.opportunities import Opportunity
    from database.models.pipeline_runs import PipelineRun
    from database.models.profiles import Profile
    from database.models.scheduler_state import SchedulerState
    from database.models.searches import Search
    from database.models.sources import Source


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4,
    )
    email: Mapped[str] = mapped_column(
        String(320), unique=True, nullable=False, index=True,
    )
    password_hash: Mapped[str] = mapped_column(
        String(255), nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False,
    )
    is_verified: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False,
    )
    last_login_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False,
    )

    profile: Mapped[Optional[Profile]] = relationship(
        "Profile", back_populates="user", uselist=False, cascade="all, delete-orphan",
    )
    sources: Mapped[List[Source]] = relationship(
        "Source", back_populates="user", cascade="all, delete-orphan",
    )
    searches: Mapped[List[Search]] = relationship(
        "Search", back_populates="user", cascade="all, delete-orphan",
    )
    opportunities: Mapped[List[Opportunity]] = relationship(
        "Opportunity", back_populates="user", cascade="all, delete-orphan",
    )
    bookmarks: Mapped[List[Bookmark]] = relationship(
        "Bookmark", back_populates="user", cascade="all, delete-orphan",
    )
    notifications: Mapped[List[Notification]] = relationship(
        "Notification", back_populates="user", cascade="all, delete-orphan",
    )
    application_settings: Mapped[Optional[ApplicationSettings]] = relationship(
        "ApplicationSettings", back_populates="user", uselist=False, cascade="all, delete-orphan",
    )
    pipeline_runs: Mapped[List[PipelineRun]] = relationship(
        "PipelineRun", back_populates="user", cascade="all, delete-orphan",
    )
    scheduler_states: Mapped[List[SchedulerState]] = relationship(
        "SchedulerState", back_populates="user", cascade="all, delete-orphan",
    )
