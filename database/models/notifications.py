"""Notification model."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base

if TYPE_CHECKING:
    from database.models.profiles import Profile
    from database.models.users import User


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    profile_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("profiles.id", ondelete="CASCADE"), nullable=True, index=True,
    )
    type_: Mapped[str] = mapped_column(
        "type", String(20), nullable=False,
    )
    title: Mapped[str] = mapped_column(
        String(200), nullable=False,
    )
    message: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True,
    )
    is_read: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False,
    )
    read_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    channel: Mapped[str] = mapped_column(
        String(20), default="in_app", nullable=False,
    )
    delivered_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    metadata_json: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True,
    )
    email_to: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True,
    )
    digest_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, nullable=True, index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )

    user: Mapped[User] = relationship(
        "User", back_populates="notifications",
    )
    profile: Mapped[Optional[Profile]] = relationship(
        "Profile", back_populates="notifications",
    )
