"""Search pipeline tests."""

from __future__ import annotations

from unittest.mock import patch
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from database.models.profiles import Profile
from database.models.users import User



# ── helpers ──────────────────────────────────────────────────────────


def _user(db_session: Session) -> uuid.UUID:
    uid = uuid4()
    db_session.add(User(id=uid, email=f"{uid}@test.com", password_hash="test-hash"))
    db_session.flush()
    return uid


def _profile(db_session: Session) -> Profile:
    uid = _user(db_session)
    p = Profile(id=uuid4(), user_id=uid)
    db_session.add(p)
    db_session.flush()
    return p


from services.search_pipeline import (
    CallbackNotifier,
    LoggingNotifier,
    PipelineConfig,
    PipelineEvent,
    PipelineNotifier,
    PipelineResult,
    SearchPipeline,
)
from services.search_pipeline.steps.base import PipelineStep
from services.search_pipeline.steps.content_extractor import ContentExtractorStep
from services.search_pipeline.steps.notifier import NotifierStep
from services.search_pipeline.steps.opportunity_creator import OpportunityCreator
from services.search_pipeline.steps.query_generator import QueryGenerator
from services.search_pipeline.steps.ranking import AIRankingStep
from services.search_pipeline.steps.search_executor import SearchExecutor


class TestPipelineEvent:
    def test_default_fields(self) -> None:
        e = PipelineEvent()
        assert e.step == ""
        assert e.status == ""
        assert e.message == ""
        assert e.data == {}

    def test_all_fields(self) -> None:
        e = PipelineEvent(step="Test", status="completed", message="done", data={"key": "val"})
        assert e.step == "Test"
        assert e.data["key"] == "val"


class TestPipelineConfig:
    def test_defaults(self) -> None:
        c = PipelineConfig()
        assert c.query_generator_enabled is True
        assert c.search_executor_enabled is True
        assert c.content_extractor_enabled is True
        assert c.opportunity_creator_enabled is True
        assert c.ai_ranking_enabled is True
        assert c.notifier_enabled is True
        assert c.query_count == 5
        assert c.search_provider == "dummy"
        assert c.search_result_count == 10

    def test_custom_values(self) -> None:
        c = PipelineConfig(query_count=3, ai_ranking_enabled=False)
        assert c.query_count == 3
        assert c.ai_ranking_enabled is False


class TestPipelineResult:
    def test_defaults(self) -> None:
        r = PipelineResult()
        assert r.success is False
        assert r.queries_generated == []
        assert r.search_results_count == 0
        assert r.error == ""


class TestLoggingNotifier:
    def test_on_event_does_not_raise(self) -> None:
        n = LoggingNotifier()
        n.on_event(PipelineEvent(step="S", status="started", message="test"))


class TestCallbackNotifier:
    def test_on_event_calls_callback(self) -> None:
        events: list[PipelineEvent] = []

        def cb(e: PipelineEvent) -> None:
            events.append(e)

        n = CallbackNotifier(callback=cb)
        n.on_event(PipelineEvent(step="S", status="done", message="ok"))
        assert len(events) == 1
        assert events[0].step == "S"


class TestQueryGenerator:
    @pytest.mark.asyncio
    @patch("services.search_pipeline.steps.query_generator.generate_with_fallback")
    async def test_execute_with_mocked_fallback(self, mock_fallback) -> None:
        from services.ai import AIResponse

        mock_fallback.return_value = (
            AIResponse(
                content='["python developer", "fastapi jobs"]',
                model="test-model",
                provider="OpenRouter",
            ),
            "openrouter",
        )

        profile = Profile(
            id=uuid4(),
            user_id=uuid4(),
            skills=["Python", "FastAPI", "SQL"],
            preferred_locations=["Remote"],
        )
        step = QueryGenerator(query_count=3)
        ctx = {"profile": profile}
        result = await step.execute(ctx)
        assert "queries" in result
        assert len(result["queries"]) > 0

    @pytest.mark.asyncio
    async def test_execute_missing_profile_raises(self) -> None:
        step = QueryGenerator()
        with pytest.raises(ValueError, match="No profile"):
            await step.execute({})


class TestSearchExecutor:
    @pytest.mark.asyncio
    async def test_execute_with_dummy_provider(self, db_session) -> None:
        uid = _user(db_session)
        profile = Profile(id=uuid4(), user_id=uid)
        step = SearchExecutor(provider_name="dummy", result_count=5)
        ctx = {"queries": ["python developer", "fastapi jobs"], "profile": profile, "db": db_session}
        result = await step.execute(ctx)
        assert "search_results" in result
        assert len(result["search_results"]) > 0

    @pytest.mark.asyncio
    async def test_execute_empty_queries(self, db_session) -> None:
        uid = _user(db_session)
        profile = Profile(id=uuid4(), user_id=uid)
        step = SearchExecutor(provider_name="dummy")
        ctx = {"queries": [], "profile": profile, "db": db_session}
        result = await step.execute(ctx)
        assert result["search_results"] == []


class TestContentExtractorStep:
    @pytest.mark.asyncio
    async def test_execute_with_valid_results(self) -> None:
        from services.search.models import SearchResult

        step = ContentExtractorStep()
        ctx = {
            "search_results": [
                SearchResult(title="Test", url="https://example.com", snippet="test page"),
            ],
        }
        result = await step.execute(ctx)
        assert "extracted_contents" in result
        assert len(result["extracted_contents"]) == 1

    @pytest.mark.asyncio
    async def test_execute_empty_results(self) -> None:
        step = ContentExtractorStep()
        ctx = {"search_results": []}
        result = await step.execute(ctx)
        assert result["extracted_contents"] == []


class TestOpportunityCreator:
    @pytest.mark.asyncio
    async def test_execute_creates_opportunities(self, db_session) -> None:
        from services.content_extractor import ExtractedContent
        from services.search.models import SearchResult

        p = _profile(db_session)
        step = OpportunityCreator(db=db_session)
        ctx = {
            "profile": p,
            "extracted_contents": [
                {
                    "search_result": SearchResult(
                        title="Python Dev", url="https://example.com/job1",
                        snippet="Build APIs",
                    ),
                    "content": ExtractedContent(
                        title="Python Dev", content="Job description here",
                        source_url="https://example.com/job1",
                    ),
                },
            ],
        }
        result = await step.execute(ctx)
        assert "opportunities" in result
        assert len(result["opportunities"]) == 1
        opp = result["opportunities"][0]
        assert opp.title == "Python Dev"

    @pytest.mark.asyncio
    async def test_execute_empty_extracted(self, db_session) -> None:
        p = _profile(db_session)
        step = OpportunityCreator(db=db_session)
        ctx = {"profile": p, "extracted_contents": []}
        result = await step.execute(ctx)
        assert result["opportunities"] == []

    @pytest.mark.asyncio
    async def test_dedup_skips_duplicate_url(self, db_session) -> None:
        from datetime import datetime, timezone

        from services.content_extractor import ExtractedContent
        from services.search.models import SearchResult

        p = _profile(db_session)

        # First run — insert the opportunity
        step1 = OpportunityCreator(db=db_session)
        ctx1 = {
            "profile": p,
            "extracted_contents": [
                {
                    "search_result": SearchResult(
                        title="Python Dev", url="https://example.com/job1",
                        snippet="Build APIs",
                    ),
                    "content": ExtractedContent(
                        title="Python Dev", content="Job description here",
                        source_url="https://example.com/job1",
                    ),
                },
            ],
        }
        result1 = await step1.execute(ctx1)
        assert len(result1["opportunities"]) == 1
        assert result1["opportunities_skipped_duplicate"] == 0
        first_opp = result1["opportunities"][0]
        first_id = first_opp.id
        first_seen = first_opp.last_seen_at

        # Second run — same URL should skip creation but update last_seen_at
        step2 = OpportunityCreator(db=db_session)
        ctx2 = {
            "profile": p,
            "extracted_contents": [
                {
                    "search_result": SearchResult(
                        title="Python Dev", url="https://example.com/job1",
                        snippet="Build APIs",
                    ),
                    "content": ExtractedContent(
                        title="Python Dev", content="Job description here",
                        source_url="https://example.com/job1",
                    ),
                },
            ],
        }
        result2 = await step2.execute(ctx2)
        assert len(result2["opportunities"]) == 1
        assert result2["opportunities_skipped_duplicate"] == 1
        second_opp = result2["opportunities"][0]
        assert second_opp.id == first_id
        assert second_opp.last_seen_at is not None
        if first_seen is not None:
            assert second_opp.last_seen_at >= first_seen

    @pytest.mark.asyncio
    async def test_dedup_empty_url_always_creates(self, db_session) -> None:
        from services.content_extractor import ExtractedContent
        from services.search.models import SearchResult

        p = _profile(db_session)

        step = OpportunityCreator(db=db_session)
        ctx = {
            "profile": p,
            "extracted_contents": [
                {
                    "search_result": SearchResult(title="No URL Job", url=""),
                    "content": ExtractedContent(content="desc"),
                },
            ],
        }
        result1 = await step.execute(ctx)
        assert len(result1["opportunities"]) == 1
        assert result1["opportunities_skipped_duplicate"] == 0

        result2 = await step.execute(ctx)
        assert len(result2["opportunities"]) == 1
        assert result2["opportunities_skipped_duplicate"] == 0

    @pytest.mark.asyncio
    async def test_dedup_updates_last_seen_at(self, db_session) -> None:
        from datetime import datetime, timedelta, timezone

        from services.content_extractor import ExtractedContent
        from services.search.models import SearchResult

        p = _profile(db_session)

        # Insert a direct opportunity with a last_seen_at in the past
        from database.models.opportunities import Opportunity

        past = datetime.now(timezone.utc) - timedelta(days=30)
        opp = Opportunity(
            id=uuid4(), user_id=p.user_id,
            title="Old", url="https://example.com/old",
            discovered_at=past, last_seen_at=past,
        )
        db_session.add(opp)
        db_session.flush()

        step = OpportunityCreator(db=db_session)
        ctx = {
            "profile": p,
            "extracted_contents": [
                {
                    "search_result": SearchResult(
                        title="Old", url="https://example.com/old",
                    ),
                    "content": ExtractedContent(source_url="https://example.com/old"),
                },
            ],
        }
        result = await step.execute(ctx)
        assert result["opportunities_skipped_duplicate"] == 1
        updated = result["opportunities"][0]
        assert updated.last_seen_at is not None
        assert updated.last_seen_at > past


class TestRanking:
    @pytest.mark.asyncio
    @patch("services.opportunity_scorer.scorer.generate_with_fallback")
    async def test_execute_with_mocked_fallback(self, mock_fallback, db_session) -> None:
        from datetime import datetime, timezone

        from database.models.opportunities import Opportunity
        from services.ai import AIResponse

        mock_fallback.return_value = (
            AIResponse(
                content='{"relevance_score": 85, "summary": "Good", '
                        '"pros": [], "cons": [], '
                        '"required_skills": [], "missing_skills": [], '
                        '"application_deadline": "", "ranking_explanation": ""}',
                model="test-model",
                provider="OpenRouter",
            ),
            "openrouter",
        )

        uid = _user(db_session)
        profile = Profile(id=uuid4(), user_id=uid, skills=["Python"])
        opp = Opportunity(
            id=uuid4(), user_id=uid,
            title="Python Job", description="Build stuff",
            discovered_at=datetime.now(timezone.utc),
        )
        db_session.add(opp)
        db_session.flush()

        step = AIRankingStep(db=db_session)
        ctx = {"profile": profile, "opportunities": [opp]}
        result = await step.execute(ctx)
        assert "scored_opportunities" in result
        assert len(result["scored_opportunities"]) == 1

    @pytest.mark.asyncio
    async def test_execute_no_opportunities(self, db_session) -> None:
        uid = _user(db_session)
        profile = Profile(id=uuid4(), user_id=uid)
        step = AIRankingStep(db=db_session)
        ctx = {"profile": profile, "opportunities": []}
        result = await step.execute(ctx)
        assert result["scored_opportunities"] == []


class TestNotifierStep:
    @pytest.mark.asyncio
    async def test_creates_opportunity_notifications(self, db_session) -> None:
        events: list[PipelineEvent] = []

        class TestNotifier(PipelineNotifier):
            def on_event(self, event: PipelineEvent) -> None:
                events.append(event)

        from services.opportunity_scorer.scorer import ScoredOpportunity
        from database.repositories.notification_repository import NotificationRepository

        p = _profile(db_session)
        user_id = p.user_id

        # Create scored opportunities with varying scores
        scored_opps = [
            ScoredOpportunity(
                opportunity_id="opp1", title="Intern Role", url="http://example.com/1",
                relevance_score=75,
            ),
            ScoredOpportunity(
                opportunity_id="opp2", title="Low Score Role", url="http://example.com/2",
                relevance_score=40,
            ),
        ]

        step = NotifierStep(db=db_session, notifier=TestNotifier())
        ctx = {
            "profile": p,
            "opportunities": ["o1", "o2"],
            "scored_opportunities": scored_opps,
        }
        result = await step.execute(ctx)

        assert result["notifications_created"] == 1
        assert len(events) == 1
        assert "opportunities found" in events[0].message

        repo = NotificationRepository(db_session)
        notifs = repo.list_by_user_id(user_id, limit=100)

        assert len(notifs) == 2
        assert notifs[0].type_ in ("opportunity", "pipeline_run")
        assert notifs[1].type_ in ("opportunity", "pipeline_run")

    @pytest.mark.asyncio
    async def test_caps_opportunity_notifications(self, db_session) -> None:
        from services.opportunity_scorer.scorer import ScoredOpportunity

        p = _profile(db_session)

        scored_opps = [
            ScoredOpportunity(
                opportunity_id=f"opp{i}", title=f"Role {i}", url=f"http://example.com/{i}",
                relevance_score=75,
            )
            for i in range(15)
        ]

        step = NotifierStep(db=db_session, notifier=None)
        ctx = {
            "profile": p,
            "opportunities": list(range(15)),
            "scored_opportunities": scored_opps,
        }
        result = await step.execute(ctx)

        assert result["notifications_created"] == 10

    @pytest.mark.asyncio
    async def test_respects_score_threshold(self, db_session) -> None:
        from services.opportunity_scorer.scorer import ScoredOpportunity

        p = _profile(db_session)

        scored_opps = [
            ScoredOpportunity(
                opportunity_id="opp1", title="Low Score", url="http://example.com",
                relevance_score=30,
            ),
        ]

        step = NotifierStep(db=db_session, notifier=None)
        ctx = {
            "profile": p,
            "opportunities": ["o1"],
            "scored_opportunities": scored_opps,
        }
        result = await step.execute(ctx)

        assert result["notifications_created"] == 0


class TestSearchPipeline:
    @pytest.mark.asyncio
    @patch("services.search_pipeline.steps.query_generator.generate_with_fallback")
    @patch("services.opportunity_scorer.scorer.generate_with_fallback")
    async def test_full_pipeline_with_mocked_ai(
        self, mock_scorer_fallback, mock_query_fallback, db_session
    ) -> None:
        from services.ai import AIResponse

        mock_query_fallback.return_value = (
            AIResponse(
                content='["python dev", "fastapi jobs"]',
                model="test-model", provider="OpenRouter",
            ),
            "openrouter",
        )

        mock_scorer_fallback.return_value = (
            AIResponse(
                content='{"relevance_score": 85, "summary": "Good", '
                        '"pros": [], "cons": [], '
                        '"required_skills": [], "missing_skills": [], '
                        '"application_deadline": "", "ranking_explanation": ""}',
                model="test-model", provider="OpenRouter",
            ),
            "openrouter",
        )

        p = _profile(db_session)
        p.skills = ["Python", "FastAPI"]
        p.preferred_locations = ["Remote"]
        db_session.flush()

        config = PipelineConfig(
            query_count=2,
            search_provider="dummy",
            search_result_count=3,
            ai_ranking_enabled=True,
            content_extractor_enabled=True,
        )
        pipeline = SearchPipeline(db=db_session, config=config)
        result = await pipeline.run(p)
        assert result.success is True

    @pytest.mark.asyncio
    @patch("services.search_pipeline.steps.query_generator.generate_with_fallback")
    async def test_pipeline_without_ranking(
        self, mock_query_fallback, db_session
    ) -> None:
        from services.ai import AIResponse

        mock_query_fallback.return_value = (
            AIResponse(
                content='["python dev"]',
                model="test-model", provider="OpenRouter",
            ),
            "openrouter",
        )

        p = _profile(db_session)
        p.skills = ["Python"]
        db_session.flush()

        config = PipelineConfig(
            ai_ranking_enabled=False,
            query_count=1,
            search_provider="dummy",
            search_result_count=2,
        )
        pipeline = SearchPipeline(db=db_session, config=config)
        result = await pipeline.run(p)
        assert result.success is True
        assert result.opportunities_scored == 0

    @pytest.mark.asyncio
    async def test_pipeline_disabled_steps(self, db_session) -> None:
        p = _profile(db_session)
        p.skills = ["Python"]
        db_session.flush()

        config = PipelineConfig(
            query_generator_enabled=False,
            search_executor_enabled=False,
            content_extractor_enabled=False,
            opportunity_creator_enabled=False,
            ai_ranking_enabled=False,
        )
        pipeline = SearchPipeline(db=db_session, config=config)
        result = await pipeline.run(p)
        assert result.success is True
        assert result.queries_generated == []
        assert result.opportunities_created == 0