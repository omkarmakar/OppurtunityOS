"""ApplicationSettings repository."""

from __future__ import annotations

from database.models.application_settings import ApplicationSettings
from database.repositories.base import BaseRepository


class ApplicationSettingsRepository(BaseRepository[ApplicationSettings]):
    _model = ApplicationSettings
