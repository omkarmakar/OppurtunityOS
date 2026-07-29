"""Quota state model — persists per-provider API quota from RapidAPI response headers.

Stores the last-known remaining requests, limit, and reset timestamp for each
job board provider so the weekly scheduler can make quota-aware decisions
without burning API calls.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Float, Integer, String, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from database.base import Base


class QuotaState(Base):
    __tablename__ = "quota_state"

    __table_args__ = (
        UniqueConstraint(
            "provider_name",
            name="uq_quota_state_provider",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4,
    )
    provider_name: Mapped[str] = mapped_column(
        String(100), nullable=False, index=True,
    )
    remaining: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True,
    )
    quota_limit: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True,
    )
    reset_at: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True,
    )
    last_updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
