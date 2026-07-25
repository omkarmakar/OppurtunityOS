"""Bookmark repository."""

from __future__ import annotations

from database.models.bookmarks import Bookmark
from database.repositories.base import BaseRepository


class BookmarkRepository(BaseRepository[Bookmark]):
    _model = Bookmark
