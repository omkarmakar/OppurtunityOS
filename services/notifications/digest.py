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
from database.models.opportunities import Opportunity
from database.repositories.notification_repository import NotificationRepository
from database.repositories.opportunity_repository import OpportunityRepository
from services.notifications.digest_formatter import DigestFormatter
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
        self._opp_repo = OpportunityRepository(db)
        self._email = email_provider
        self._settings = settings or DigestSettings()

    def run(
        self,
        user_id: uuid.UUID,
        profile_id: uuid.UUID | None = None,
        profile_name: str = "",
        user_email: str = "",
    ) -> dict[str, Any]:
        """Create a digest of unread notifications for the given user and profile.

        When ``profile_id`` is provided only notifications scoped to that
        profile are included.  The profile name appears in the email subject
        so multiple per-profile digests are distinguishable at a glance.
        """
        unread = self._repo.list_unread_by_channel(
            user_id, "in_app",
            limit=self._settings.max_opportunities,
            profile_id=profile_id,
        )
        if not unread:
            return {"notifications_count": 0, "email_sent": False, "digest_id": None}

        # Load opportunities for context
        opportunities = {}
        for notif in unread:
            if notif.opportunity_id:
                try:
                    opp = self._opp_repo.get_by_id(notif.opportunity_id)
                    if opp:
                        opportunities[str(opp.id)] = opp
                except Exception:
                    pass

        digest_id = uuid.uuid4()
        summary = self._build_summary(unread)

        digest_notif = Notification(
            user_id=user_id,
            profile_id=profile_id,
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
        if self._email and user_email:
            subject = (
                f"OpportunityOS Digest — {profile_name} — {len(unread)} new opportunities"
                if profile_name
                else f"Daily Digest — {len(unread)} new notification(s)"
            )
            
            # Use enhanced HTML formatter for email
            html_body = DigestFormatter.format_digest_html(unread, opportunities)
            
            email_sent = self._email.send(
                str(user_id),
                subject,
                summary["text"],  # Fallback text version
                email_to=user_email,
                html_body=html_body,
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
            type_counts[n.type_] = type_counts.get(n.type_, 0) + 1
            
            if n.type_ == "opportunity":
                # For opportunity notifications, include score and URL from metadata
                try:
                    metadata = json.loads(n.metadata_json) if n.metadata_json else {}
                    score = metadata.get("score", 0)
                    url = metadata.get("url", "")
                    line = f"  \u2022 {n.title} (score {score:.0f}/100)"
                    if url:
                        line += f"\n    {url}"
                    lines.append(line)
                except Exception:
                    lines.append(f"  \u2022 {n.title}")
            else:
                # For other types, use title
                lines.append(f"  \u2022 [{n.type_}] {n.title}")
        
        return {
            "text": "\n".join(lines),
            "metadata": {
                "total": len(notifications),
                "type_counts": type_counts,
            },
        }
