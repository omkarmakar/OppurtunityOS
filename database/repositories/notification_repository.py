"""Notification repository."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select, update, func

from database.models.notifications import Notification
from database.repositories.base import BaseRepository


class NotificationRepository(BaseRepository[Notification]):
    _model = Notification

    def list_by_user_id(
        self,
        user_id: uuid.UUID,
        *,
        limit: int = 50,
        offset: int = 0,
        unread_only: bool = False,
        channel: str | None = None,
    ) -> list[Notification]:
        stmt = select(Notification).where(Notification.user_id == user_id).order_by(Notification.created_at.desc())
        if unread_only:
            stmt = stmt.where(Notification.is_read == False)
        if channel:
            stmt = stmt.where(Notification.channel == channel)
        stmt = stmt.offset(offset).limit(limit)
        return list(self._session.scalars(stmt).all())

    def count_unread(self, user_id: uuid.UUID) -> int:
        stmt = select(func.count()).select_from(Notification).where(
            Notification.user_id == user_id,
            Notification.is_read == False,
        )
        result = self._session.execute(stmt)
        return result.scalar_one()

    def mark_as_read(self, notification_id: uuid.UUID) -> Notification | None:
        notif = self.get(notification_id)
        if not notif:
            return None
        notif.is_read = True
        notif.read_at = datetime.now(timezone.utc)
        self.update(notif)
        return notif

    def mark_all_as_read(self, user_id: uuid.UUID) -> int:
        now = datetime.now(timezone.utc)
        stmt = (
            update(Notification)
            .where(Notification.user_id == user_id, Notification.is_read == False)
            .values(is_read=True, read_at=now)
        )
        result = self._session.execute(stmt)
        self._session.flush()
        return result.rowcount

    def list_unread_by_channel(
        self,
        user_id: uuid.UUID,
        channel: str,
        limit: int = 50,
        profile_id: uuid.UUID | None = None,
    ) -> list[Notification]:
        stmt = (
            select(Notification)
            .where(
                Notification.user_id == user_id,
                Notification.is_read == False,
                Notification.channel == channel,
            )
            .order_by(Notification.created_at.desc())
            .limit(limit)
        )
        if profile_id is not None:
            stmt = stmt.where(Notification.profile_id == profile_id)
        else:
            stmt = stmt.where(Notification.profile_id.is_(None))
        return list(self._session.scalars(stmt).all())

    def list_by_digest(self, digest_id: uuid.UUID) -> list[Notification]:
        stmt = (
            select(Notification)
            .where(Notification.digest_id == digest_id)
            .order_by(Notification.created_at.asc())
        )
        return list(self._session.scalars(stmt).all())
