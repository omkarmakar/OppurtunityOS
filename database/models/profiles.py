"""User profile model."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional

from sqlalchemy import JSON, DateTime, ForeignKey, Index, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base

if TYPE_CHECKING:
    from database.models.users import User


class Profile(Base):
    __tablename__ = "profiles"

    __table_args__ = (
        Index("ix_profiles_user_id", "user_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=False,
    )
    name: Mapped[str] = mapped_column(
        String(100), default="Profile 1", nullable=False,
    )
    display_name: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True,
    )
    avatar_url: Mapped[Optional[str]] = mapped_column(
        String(500), nullable=True,
    )
    bio: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True,
    )
    education: Mapped[Optional[list[dict[str, Any]]]] = mapped_column(
        JSON, nullable=True,
    )
    experience: Mapped[Optional[list[dict[str, Any]]]] = mapped_column(
        JSON, nullable=True,
    )
    skills: Mapped[Optional[list[str]]] = mapped_column(
        JSON, nullable=True,
    )
    preferred_locations: Mapped[Optional[list[str]]] = mapped_column(
        JSON, nullable=True,
    )
    salary_expectations: Mapped[Optional[str]] = mapped_column(
        String(200), nullable=True,
    )
    target_companies: Mapped[Optional[list[str]]] = mapped_column(
        JSON, nullable=True,
    )
    keywords: Mapped[Optional[list[str]]] = mapped_column(
        JSON, nullable=True,
    )
    resume_path: Mapped[Optional[str]] = mapped_column(
        String(500), nullable=True,
    )
    linkedin_url: Mapped[Optional[str]] = mapped_column(
        String(500), nullable=True,
    )
    github_url: Mapped[Optional[str]] = mapped_column(
        String(500), nullable=True,
    )
    portfolio: Mapped[Optional[str]] = mapped_column(
        String(500), nullable=True,
    )
    projects: Mapped[Optional[list[dict[str, str]]]] = mapped_column(
        JSON, nullable=True,
    )
    preferences: Mapped[Optional[dict[str, Any]]] = mapped_column(
        JSON, nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False,
    )

    user: Mapped[User] = relationship(
        "User", back_populates="profiles",
    )