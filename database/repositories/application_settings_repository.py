"""ApplicationSettings repository."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select

from database.models.application_settings import ApplicationSettings
from database.repositories.base import BaseRepository


class ApplicationSettingsRepository(BaseRepository[ApplicationSettings]):
    _model = ApplicationSettings

    def get_by_user_id(self, user_id: UUID) -> ApplicationSettings | None:
        stmt = select(self._model).where(self._model.user_id == user_id)
        return self._session.scalar(stmt)

    def upsert(self, user_id: UUID, **kwargs) -> ApplicationSettings:
        existing = self.get_by_user_id(user_id)
        if existing:
            for key, value in kwargs.items():
                setattr(existing, key, value)
            self.update(existing)
            return existing
        settings = self._model(user_id=user_id, **kwargs)
        self.add(settings)
        return settings
