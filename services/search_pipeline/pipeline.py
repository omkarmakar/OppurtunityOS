"""Search pipeline orchestrator — runs modular steps in sequence."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from database.models.profiles import Profile
from services.search_pipeline.notifier import (
    LoggingNotifier,
    PipelineEvent,
    PipelineNotifier,
)
from services.search_pipeline.steps.base import PipelineStep
from services.search_pipeline.steps.content_extractor import ContentExtractorStep
from services.search_pipeline.steps.notifier import NotifierStep
from services.search_pipeline.steps.opportunity_creator import OpportunityCreator
from services.search_pipeline.steps.query_generator import QueryGenerator
from services.search_pipeline.steps.ranking import AIRankingStep
from services.search_pipeline.steps.search_executor import SearchExecutor


@dataclass
class PipelineConfig:
    query_generator_enabled: bool = True
    search_executor_enabled: bool = True
    content_extractor_enabled: bool = True
    opportunity_creator_enabled: bool = True
    ai_ranking_enabled: bool = True
    notifier_enabled: bool = True

    query_generator_provider: str = ""
    query_generator_model: str = ""
    query_count: int = 5
    search_provider: str = "dummy"
    search_result_count: int = 10
    ai_ranking_provider: str = ""
    ai_ranking_model: str = ""

    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class PipelineResult:
    success: bool = False
    queries_generated: list[str] = field(default_factory=list)
    search_results_count: int = 0
    pages_extracted: int = 0
    opportunities_created: int = 0
    opportunities_scored: int = 0
    notifications_sent: int = 0
    error: str = ""
    step_results: dict[str, Any] = field(default_factory=dict)


class SearchPipeline:
    def __init__(
        self,
        db: Session,
        config: PipelineConfig | None = None,
        notifier: PipelineNotifier | None = None,
    ) -> None:
        self._db = db
        self._config = config or PipelineConfig()
        self._notifier = notifier or LoggingNotifier()
        self._steps: list[PipelineStep] = []

    def _build_steps(self) -> None:
        self._steps = []

        if self._config.query_generator_enabled:
            self._steps.append(
                QueryGenerator(
                    provider=self._config.query_generator_provider,
                    model=self._config.query_generator_model,
                    query_count=self._config.query_count,
                )
            )

        if self._config.search_executor_enabled:
            self._steps.append(
                SearchExecutor(
                    provider_name=self._config.search_provider,
                    result_count=self._config.search_result_count,
                )
            )

        if self._config.content_extractor_enabled:
            self._steps.append(ContentExtractorStep())

        if self._config.opportunity_creator_enabled:
            self._steps.append(OpportunityCreator(db=self._db))

        if self._config.ai_ranking_enabled:
            self._steps.append(
                AIRankingStep(
                    db=self._db,
                    provider=self._config.ai_ranking_provider,
                    model=self._config.ai_ranking_model,
                )
            )

        if self._config.notifier_enabled:
            self._steps.append(NotifierStep(notifier=self._notifier))

    def _emit(self, step: str, status: str, message: str, data: dict | None = None) -> None:
        self._notifier.on_event(
            PipelineEvent(
                step=step,
                status=status,
                message=message,
                data=data or {},
            )
        )

    async def run(self, profile: Profile) -> PipelineResult:
        self._build_steps()
        result = PipelineResult()

        ctx: dict[str, Any] = {
            "profile": profile,
            "db": self._db,
        }

        self._emit("pipeline", "started", "Pipeline started", {"user_id": str(profile.user_id)})

        for step in self._steps:
            try:
                self._emit(step.name, "started", f"Running step: {step.name}")
                ctx = await step.execute(ctx)
                self._emit(step.name, "completed", f"Step completed: {step.name}")
            except Exception as e:
                msg = f"Step '{step.name}' failed: {e}"
                self._emit(step.name, "failed", msg)
                result.success = False
                result.error = msg
                return result

        result.success = True
        result.queries_generated = ctx.get("queries", [])
        result.search_results_count = len(ctx.get("search_results", []))
        result.pages_extracted = len(ctx.get("extracted_contents", []))
        result.opportunities_created = len(ctx.get("opportunities", []))
        result.opportunities_scored = len(ctx.get("scored_opportunities", []))
        result.notifications_sent = 1
        result.step_results = ctx

        self._emit("pipeline", "completed", "Pipeline finished", {
            "opportunities": result.opportunities_created,
            "scored": result.opportunities_scored,
        })

        return result
