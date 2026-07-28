"""Profile repository."""

from __future__ import annotations

from typing import Optional

from database.models.profiles import Profile
from database.repositories.base import BaseRepository


class ProfileRepository(BaseRepository[Profile]):
    _model = Profile

    def get_by_user_id(self, user_id: object) -> Optional[Profile]:
        """Return the user's first/oldest profile if multiple exist.

        New code should prefer ``get_by_id(profile_id)`` or
        ``list_by_user_id(user_id)`` instead.
        """
        return (
            self._session.query(Profile)
            .filter(Profile.user_id == user_id)
            .order_by(Profile.created_at.asc())
            .first()
        )

    def list_by_user_id(self, user_id: object) -> list[Profile]:
        """Return all profiles for a user, ordered by creation date."""
        return (
            self._session.query(Profile)
            .filter(Profile.user_id == user_id)
            .order_by(Profile.created_at.asc())
            .all()
        )

    def count_by_user_id(self, user_id: object) -> int:
        """Return the number of profiles for a user."""
        return (
            self._session.query(Profile)
            .filter(Profile.user_id == user_id)
            .count()
        )

    def upsert(self, profile: Profile) -> Profile:
        existing = self.get_by_user_id(profile.user_id)
        if existing:
            for key, value in profile.__dict__.items():
                if key != "_sa_instance_state" and value is not None:
                    setattr(existing, key, value)
            self._session.flush()
            return existing
        self._session.add(profile)
        self._session.flush()
        return profile