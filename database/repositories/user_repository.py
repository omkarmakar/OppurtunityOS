"""User repository."""

from __future__ import annotations

import logging
import uuid

from sqlalchemy.exc import IntegrityError

from database.models.users import User
from database.repositories.base import BaseRepository

logger = logging.getLogger(__name__)


class UserRepository(BaseRepository[User]):
    _model = User

    def get_by_email(self, email: str) -> User | None:
        """Return the User with the given email, or None."""
        return self._session.query(User).filter(User.email == email).first()

    def get_or_create(self, user_id: uuid.UUID, email: str = "") -> User:
        """Return the User row for *user_id*, creating it if absent.

        When creating a new row the caller should supply a real *email*;
        if none is provided a synthetic placeholder is used so the NOT NULL
        constraint is satisfied.  The placeholder is intentionally invalid
        (no ``@``) so it will never match a real delivery address.

        Args:
            user_id: UUID primary key for the user.
            email:   Email address to store when creating a new row.
                     Ignored when the row already exists.

        Returns:
            The persisted User instance.
        """
        existing = self.get(user_id)
        if existing is not None:
            return existing

        effective_email = email if email else f"placeholder-{user_id}@no-email.invalid"
        user = User(
            id=user_id,
            email=effective_email,
            # Empty hash — this row is created automatically to satisfy FK
            # constraints; it is not a proper auth account.
            password_hash="",
        )
        try:
            self._session.add(user)
            self._session.flush()
        except IntegrityError:
            # Another concurrent path already inserted the row (race or
            # duplicate-call); roll back to the savepoint and re-fetch.
            self._session.rollback()
            existing = self.get(user_id)
            if existing is not None:
                return existing
            raise
        logger.debug("get_or_create: created User row for user_id=%s", user_id)
        return user
