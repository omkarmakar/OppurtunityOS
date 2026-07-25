"""User repository."""

from __future__ import annotations

from database.models.users import User
from database.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    _model = User
