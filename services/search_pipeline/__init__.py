"""Search pipeline — modular end-to-end opportunity discovery flow.

Steps (each a PipelineStep subclass):
  1. QueryGenerator    — generates search queries from a user profile
  2. SearchExecutor    — runs queries through a SearchProvider
  3. ContentExtractorStep — extracts clean text from result URLs
  4. OpportunityCreator — creates/updates Opportunity DB records
  5. AIRankingStep     — scores opportunities via AI
  6. NotifierStep      — emits signals/events for GUI integration

Orchestrator:
  SearchPipeline      — runs enabled steps in sequence

Usage::

    pipeline = SearchPipeline(db_session)
    result = await pipeline.run(profile)
"""

from services.search_pipeline.notifier import (
    CallbackNotifier,
    LoggingNotifier,
    PipelineEvent,
    PipelineNotifier,
)
from services.search_pipeline.pipeline import PipelineConfig, PipelineResult, SearchPipeline
from services.search_pipeline.steps.base import PipelineStep
from services.search_pipeline.steps.content_extractor import ContentExtractorStep
from services.search_pipeline.steps.notifier import NotifierStep
from services.search_pipeline.steps.opportunity_creator import OpportunityCreator
from services.search_pipeline.steps.query_generator import QueryGenerator
from services.search_pipeline.steps.ranking import AIRankingStep
from services.search_pipeline.steps.search_executor import SearchExecutor

__all__ = [
    "SearchPipeline",
    "PipelineStep",
    "PipelineConfig",
    "PipelineResult",
    "PipelineNotifier",
    "PipelineEvent",
    "LoggingNotifier",
    "CallbackNotifier",
    "QueryGenerator",
    "SearchExecutor",
    "ContentExtractorStep",
    "OpportunityCreator",
    "AIRankingStep",
    "NotifierStep",
]
