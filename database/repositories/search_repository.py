"""Search repository."""

from __future__ import annotations

from database.models.searches import Search
from database.repositories.base import BaseRepository


class SearchRepository(BaseRepository[Search]):
    _model = Search
