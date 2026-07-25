"""SchedulerState repository.

Provides get_or_create and update_last_run for the per-user, per-task
scheduler state rows that back the calendar-window run-condition logic.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

from sqlalchemy import select

from database.models.scheduler_state import SchedulerState
from database.repositories.base import BaseRepository


class SchedulerStateRepository(BaseRepository[SchedulerState]):
    _model = SchedulerState

    def get_by_user_and_task(
        self, user_id: uuid.UUID, task_name: str
    ) -> SchedulerState | None:
        """Return the state row for *(user_id, task_name)*, or None."""
        stmt = (
            select(self._model)
            .where(self._model.user_id == user_id)
            .where(self._model.task_name == task_name)
        )
        return self._session.scalar(stmt)

    def get_or_create(
        self, user_id: uuid.UUID, task_name: str
    ) -> SchedulerState:
        """Return the existing state row or insert a fresh one.

        The new row has ``last_run_date=None`` and ``last_run_at=None``,
        meaning "never ran".  Call :meth:`update_last_run` after a
        successful task execution.

        Args:
            user_id:   Owner of the task state.
            task_name: Logical name matching ``ScheduledTask.name``.

        Returns:
            The persisted :class:`SchedulerState` instance.
        """
        existing = self.get_by_user_and_task(user_id, task_name)
        if existing is not None:
            return existing
        state = SchedulerState(user_id=user_id, task_name=task_name)
        self._session.add(state)
        self._session.flush()
        return state

    def update_last_run(
        self,
        user_id: uuid.UUID,
        task_name: str,
        run_date: date,
        run_at: datetime | None = None,
    ) -> SchedulerState:
        """Record a successful run.

        Args:
            user_id:   Owner of the task state.
            task_name: Logical name matching ``ScheduledTask.name``.
            run_date:  LOCAL calendar date the task ran on (the caller is
                       responsible for converting UTC→local before passing
                       this in).
            run_at:    Optional UTC timestamp of completion; defaults to
                       ``datetime.now(timezone.utc)`` when omitted.

        Returns:
            The updated :class:`SchedulerState` instance.
        """
        state = self.get_or_create(user_id, task_name)
        state.last_run_date = run_date
        state.last_run_at = run_at or datetime.now(timezone.utc)
        self._session.flush()
        return state
