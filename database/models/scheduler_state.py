"""Scheduler state model — persists per-user, per-profile, per-task last-run information.

Stores the LOCAL calendar date on which a task last ran successfully so that
window-based scheduling can answer "has this task already run today?" across
process restarts.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Date, DateTime, ForeignKey, String, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base

if TYPE_CHECKING:
    from database.models.profiles import Profile
    from database.models.users import User


class SchedulerState(Base):
    __tablename__ = "scheduler_state"

    # One row per (user_id, profile_id, task_name) tuple.
    # profile_id is NULL for user-level tasks (e.g. "digest").
    __table_args__ = (
        UniqueConstraint(
            "user_id", "profile_id", "task_name",
            name="uq_scheduler_state_user_profile_task",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    profile_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("profiles.id", ondelete="CASCADE"), nullable=True, index=True,
    )
    task_name: Mapped[str] = mapped_column(
        String(100), nullable=False,
    )
    # The LOCAL calendar date the task last completed successfully.
    # Stored as a Date (not DateTime) because the question being answered is
    # "did it run on this calendar date in the configured timezone?" —
    # the time-of-day component is irrelevant.
    last_run_date: Mapped[Optional[date]] = mapped_column(
        Date, nullable=True,
    )
    # Full UTC timestamp of the last successful completion — kept for
    # diagnostics/audit; not used in the due-check logic.
    last_run_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False,
    )

    user: Mapped[User] = relationship("User", back_populates="scheduler_states")
    profile: Mapped[Optional[Profile]] = relationship("Profile", back_populates="scheduler_states")
