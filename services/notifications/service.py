"""Notification orchestrator service."""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from core.config import AppConfig
from database.models.notifications import Notification
from database.repositories.notification_repository import NotificationRepository
from services.notifications.providers import DesktopNotificationProvider, EmailNotificationProvider

logger = logging.getLogger(__name__)


class NotificationService:
    """Creates, delivers, and queries notification records."""

    def __init__(self, db: Session, config: AppConfig | None = None) -> None:
        self._repo = NotificationRepository(db)
        self._config = config
        self._desktop_provider: DesktopNotificationProvider | None = None
        self._email_provider: EmailNotificationProvider | None = None
        self._init_providers()

    def _init_providers(self) -> None:
        if self._config and self._config.notifications.desktop_enabled:
            self._desktop_provider = DesktopNotificationProvider()
        if self._config and self._config.notifications.email_enabled:
            es = self._config.notifications.email
            self._email_provider = EmailNotificationProvider(
                host=es.smtp_host,
                port=es.smtp_port,
                username=es.smtp_username,
                password=es.smtp_password,
                use_tls=es.smtp_use_tls,
                from_address=es.from_address,
                from_name=es.from_name,
            )

    # ── create ───────────────────────────────────────────────────────

    def create_notification(
        self,
        user_id: uuid.UUID,
        type_: str,
        title: str,
        message: str | None = None,
        channel: str = "in_app",
        email_to: str | None = None,
        metadata: dict[str, Any] | None = None,
        digest_id: uuid.UUID | None = None,
        profile_id: uuid.UUID | None = None,
    ) -> Notification:
        notif = Notification(
            user_id=user_id,
            type_=type_,
            title=title,
            message=message,
            channel=channel,
            email_to=email_to,
            digest_id=digest_id,
            profile_id=profile_id,
            metadata_json=json.dumps(metadata) if metadata else None,
        )
        self._repo.add(notif)
        return notif

    # ── create + deliver ─────────────────────────────────────────────

    def send_notification(
        self,
        user_id: uuid.UUID,
        type_: str,
        title: str,
        message: str | None = None,
        channel: str = "in_app",
        email_to: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Notification:
        notif = self.create_notification(
            user_id=user_id,
            type_=type_,
            title=title,
            message=message,
            channel=channel,
            email_to=email_to,
            metadata=metadata,
        )
        if channel == "desktop" and self._desktop_provider:
            if self._desktop_provider.send(str(user_id), title, message or "", email_to=email_to):
                notif.delivered_at = datetime.now(timezone.utc)
                self._repo.update(notif)
        elif channel == "email" and self._email_provider and email_to:
            if self._email_provider.send(str(user_id), title, message or "", email_to=email_to):
                notif.delivered_at = datetime.now(timezone.utc)
                self._repo.update(notif)
        return notif

    # ── queries ──────────────────────────────────────────────────────

    def get_notifications(
        self,
        user_id: uuid.UUID,
        limit: int = 50,
        offset: int = 0,
        unread_only: bool = False,
        channel: str | None = None,
    ) -> list[Notification]:
        return self._repo.list_by_user_id(
            user_id, limit=limit, offset=offset,
            unread_only=unread_only, channel=channel,
        )

    def get_total_count(self, user_id: uuid.UUID) -> int:
        return self._repo.count(user_id=user_id)

    def count_unread(self, user_id: uuid.UUID) -> int:
        return self._repo.count_unread(user_id)

    # ── mutations ────────────────────────────────────────────────────

    def mark_as_read(self, notification_id: uuid.UUID) -> Notification | None:
        return self._repo.mark_as_read(notification_id)

    def mark_all_as_read(self, user_id: uuid.UUID) -> int:
        return self._repo.mark_all_as_read(user_id)
