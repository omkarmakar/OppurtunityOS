"""Pipeline step — sends notification about pipeline completion."""

from __future__ import annotations

from typing import Any

from services.search_pipeline.notifier import PipelineEvent, PipelineNotifier
from services.search_pipeline.steps.base import PipelineStep


class NotifierStep(PipelineStep):
    def __init__(self, notifier: PipelineNotifier) -> None:
        self._notifier = notifier

    @property
    def name(self) -> str:
        return "Notifier"

    async def execute(self, ctx: dict[str, Any]) -> dict[str, Any]:
        scored = ctx.get("scored_opportunities", [])
        opportunities = ctx.get("opportunities", [])
        profile = ctx.get("profile")

        self._notifier.on_event(
            PipelineEvent(
                step="Notifier",
                status="completed",
                message=f"Pipeline complete: {len(opportunities)} opportunities found, {len(scored)} scored",
                data={
                    "user_id": str(profile.user_id) if profile else "",
                    "opportunity_count": len(opportunities),
                    "scored_count": len(scored),
                },
            )
        )

        ctx["notification_sent"] = True
        return ctx
