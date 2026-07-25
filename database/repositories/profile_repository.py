"""Profile repository."""

from __future__ import annotations

from typing import Optional

from database.models.profiles import Profile
from database.repositories.base import BaseRepository


class ProfileRepository(BaseRepository[Profile]):
    _model = Profile

    def get_by_user_id(self, user_id: object) -> Optional[Profile]:
        return self._session.query(Profile).filter(Profile.user_id == user_id).first()

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
