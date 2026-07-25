"""PipelineRun repository."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func as sa_func, select

from database.models.pipeline_runs import PipelineRun
from database.repositories.base import BaseRepository


class PipelineRunRepository(BaseRepository[PipelineRun]):
    _model = PipelineRun

    def list_by_user_id(
        self, user_id: UUID, page: int = 1, page_size: int = 20,
    ) -> list[PipelineRun]:
        offset = (page - 1) * page_size
        stmt = (
            select(self._model)
            .where(self._model.user_id == user_id)
            .order_by(self._model.started_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        return list(self._session.scalars(stmt).all())

    def count_by_user_id(self, user_id: UUID) -> int:
        stmt = (
            select(sa_func.count())
            .select_from(self._model)
            .where(self._model.user_id == user_id)
        )
        result = self._session.execute(stmt)
        return result.scalar_one()
