"""Source repository."""

from __future__ import annotations

from database.models.sources import Source
from database.repositories.base import BaseRepository


class SourceRepository(BaseRepository[Source]):
    _model = Source
