"""Daily digest service — aggregates unread notifications into a summary."""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from core.config import DigestSettings
from database.models.notifications import Notification
from database.repositories.notification_repository import NotificationRepository
from services.notifications.providers import EmailNotificationProvider

logger = logging.getLogger(__name__)


class DailyDigestService:
    """Aggregates unread notifications and creates a digest summary."""

    def __init__(
        self,
        db: Session,
        email_provider: EmailNotificationProvider | None = None,
        settings: DigestSettings | None = None,
    ) -> None:
        self._repo = NotificationRepository(db)
        self._email = email_provider
        self._settings = settings or DigestSettings()

    def run(self, user_id: uuid.UUID, user_email: str = "") -> dict[str, Any]:
        """Create a digest of unread notifications for the given user."""
        unread = self._repo.list_unread_by_channel(
            user_id, "in_app",
            limit=self._settings.max_opportunities,
        )
        if not unread:
            return {"notifications_count": 0, "email_sent": False, "digest_id": None}

        digest_id = uuid.uuid4()
        summary = self._build_summary(unread)

        digest_notif = Notification(
            user_id=user_id,
            type_="digest",
            title="Daily Digest",
            message=summary["text"],
            channel="in_app",
            digest_id=digest_id,
            metadata_json=json.dumps(summary["metadata"]),
        )
        self._repo.add(digest_notif)

        for n in unread:
            n.digest_id = digest_id
            self._repo.update(n)

        email_sent = False
        if self._email and user_email and self._settings.include_unread_only:
            email_sent = self._email.send(
                str(user_id),
                f"Daily Digest — {len(unread)} new notification(s)",
                summary["text"],
                email_to=user_email,
            )
            if email_sent:
                digest_notif.channel = "email"
                digest_notif.delivered_at = datetime.now(timezone.utc)
                self._repo.update(digest_notif)

        return {
            "digest_id": str(digest_id),
            "notifications_count": len(unread),
            "email_sent": email_sent,
        }

    @staticmethod
    def _build_summary(notifications: list[Notification]) -> dict[str, Any]:
        lines = [f"You have {len(notifications)} new notification(s):\n"]
        type_counts: dict[str, int] = {}
        for n in notifications:
            lines.append(f"  \u2022 [{n.type_}] {n.title}")
            type_counts[n.type_] = type_counts.get(n.type_, 0) + 1
        return {
            "text": "\n".join(lines),
            "metadata": {
                "total": len(notifications),
                "type_counts": type_counts,
            },
        }
