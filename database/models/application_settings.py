"""Application settings model."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base

if TYPE_CHECKING:
    from database.models.users import User


class ApplicationSettings(Base):
    __tablename__ = "application_settings"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False,
    )
    theme: Mapped[str] = mapped_column(
        String(50), default="system", nullable=False,
    )
    language: Mapped[str] = mapped_column(
        String(10), default="en", nullable=False,
    )
    notifications_enabled: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False,
    )
    notification_preferences: Mapped[Optional[dict[str, Any]]] = mapped_column(
        JSON, nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False,
    )

    user: Mapped[User] = relationship(
        "User", back_populates="application_settings",
    )
