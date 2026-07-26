"""Pipeline step — persists notifications for new opportunities and pipeline completion."""

from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy.orm import Session

from services.notifications import NotificationService
from services.search_pipeline.notifier import PipelineEvent, PipelineNotifier
from services.search_pipeline.steps.base import PipelineStep

logger = logging.getLogger(__name__)

# Maximum number of opportunity notifications per run to avoid flooding users
MAX_OPPORTUNITY_NOTIFICATIONS = 10
# Score threshold below which we don't create individual opportunity notifications
SCORE_THRESHOLD = 50


class NotifierStep(PipelineStep):
    def __init__(self, db: Session, notifier: PipelineNotifier | None = None) -> None:
        self._db = db
        self._notifier = notifier
        self._svc = NotificationService(db)

    @property
    def name(self) -> str:
        return "Notifier"

    async def execute(self, ctx: dict[str, Any]) -> dict[str, Any]:
        scored = ctx.get("scored_opportunities", [])
        opportunities = ctx.get("opportunities", [])
        profile = ctx.get("profile")

        if not profile:
            return ctx

        user_id = profile.user_id

        # Create individual opportunity notifications for high-scoring matches
        notif_count = 0
        for opportunity in scored[:MAX_OPPORTUNITY_NOTIFICATIONS]:
            score = opportunity.relevance_score
            if score >= SCORE_THRESHOLD:
                title = f"New opportunity: {opportunity.title}"
                message = f"Score: {score:.0f}/100 — {opportunity.url or 'No URL'}"
                metadata = {
                    "opportunity_id": opportunity.opportunity_id,
                    "score": score,
                    "url": opportunity.url,
                }
                try:
                    self._svc.create_notification(
                        user_id=user_id,
                        type_="opportunity",
                        title=title,
                        message=message,
                        channel="in_app",
                        metadata=metadata,
                    )
                    notif_count += 1
                except Exception as exc:
                    logger.warning(f"Failed to create opportunity notification: {exc}")

        # Create summary notification for the pipeline run
        try:
            summary_title = f"Search complete: {len(scored)} new opportunities found"
            summary_metadata = {
                "opportunity_count": len(scored),
                "scored_count": len(scored),
                "notifications_created": notif_count,
            }
            self._svc.create_notification(
                user_id=user_id,
                type_="pipeline_run",
                title=summary_title,
                message=f"{len(opportunities)} opportunities processed, {len(scored)} matched your profile",
                channel="in_app",
                metadata=summary_metadata,
            )
        except Exception as exc:
            logger.warning(f"Failed to create pipeline summary notification: {exc}")

        # Commit the notifications
        self._db.commit()

        # Still emit the pipeline event for logging/monitoring
        if self._notifier:
            self._notifier.on_event(
                PipelineEvent(
                    step="Notifier",
                    status="completed",
                    message=f"Pipeline complete: {len(opportunities)} opportunities found, {len(scored)} scored, {notif_count} notifications created",
                    data={
                        "user_id": str(user_id),
                        "opportunity_count": len(opportunities),
                        "scored_count": len(scored),
                        "notifications_created": notif_count,
                    },
                )
            )

        ctx["notifications_created"] = notif_count
        return ctx
