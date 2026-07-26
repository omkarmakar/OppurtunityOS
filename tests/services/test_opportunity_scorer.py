"""Opportunity scorer tests."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from database.models.opportunities import Opportunity
from database.models.profiles import Profile
from services.opportunity_scorer import OpportunityScorer, ScoredOpportunity


class TestScoredOpportunity:
    def test_default_fields(self) -> None:
        s = ScoredOpportunity()
        assert s.opportunity_id == ""
        assert s.title == ""
        assert s.url == ""
        assert s.relevance_score == 0.0
        assert s.summary == ""
        assert s.pros == []
        assert s.cons == []
        assert s.required_skills == []
        assert s.missing_skills == []
        assert s.application_deadline == ""
        assert s.ranking_explanation == ""

    def test_all_fields(self) -> None:
        s = ScoredOpportunity(
            opportunity_id="123",
            title="Engineer",
            url="https://example.com/job",
            relevance_score=85.0,
            summary="Great role",
            pros=["Good pay"],
            cons=["Far away"],
            required_skills=["Python"],
            missing_skills=["Kubernetes"],
            application_deadline="2026-08-15",
            ranking_explanation="Strong match",
        )
        assert s.relevance_score == 85.0
        assert s.pros == ["Good pay"]
        assert s.missing_skills == ["Kubernetes"]


class TestOpportunityScorer:
    @pytest.mark.asyncio
    @patch("services.opportunity_scorer.scorer.generate_with_fallback")
    async def test_score_with_mocked_fallback(self, mock_fallback) -> None:
        profile = Profile(
            id=uuid4(),
            user_id=uuid4(),
            skills=["Python", "FastAPI", "SQL"],
        )

        # Mock the fallback helper to return a canned response
        from services.ai import AIResponse

        mock_fallback.return_value = (
            AIResponse(
                content='{"relevance_score": 85, "summary": "Good match", '
                        '"pros": ["Remote"], "cons": [], '
                        '"required_skills": ["Python"], "missing_skills": [], '
                        '"application_deadline": "", "ranking_explanation": "Strong"}',
                model="test-model",
                provider="OpenRouter",
            ),
            "openrouter",
        )

        scorer = OpportunityScorer(provider_name="openrouter", model_name="test-model")
        result = await scorer.score_opportunity(
            profile=profile,
            title="Python Developer",
            description="Build APIs with Python",
        )
        assert isinstance(result, ScoredOpportunity)
        assert result.title == "Python Developer"
        assert result.relevance_score == 85

    @pytest.mark.asyncio
    @patch("services.opportunity_scorer.scorer.generate_with_fallback")
    async def test_score_and_save_updates_opportunity(self, mock_fallback) -> None:
        from services.ai import AIResponse

        mock_fallback.return_value = (
            AIResponse(
                content='{"relevance_score": 90, "summary": "Great", '
                        '"pros": [], "cons": [], '
                        '"required_skills": [], "missing_skills": [], '
                        '"application_deadline": "", "ranking_explanation": ""}',
                model="test-model",
                provider="OpenRouter",
            ),
            "openrouter",
        )

        profile = Profile(
            id=uuid4(),
            user_id=uuid4(),
            skills=["Python", "Machine Learning"],
        )
        opp = Opportunity(
            id=uuid4(),
            user_id=profile.user_id,
            title="ML Engineer",
            description="Build ML models",
            url="https://example.com/ml-job",
            discovered_at=datetime.now(timezone.utc),
        )
        scorer = OpportunityScorer(provider_name="openrouter", model_name="test-model")
        result = await scorer.score_and_save(profile, opp)

        assert result.opportunity_id == str(opp.id)
        assert opp.relevance_score is not None
        assert opp.summary is not None
        assert opp.pros is not None
        assert opp.cons is not None
        assert opp.required_skills is not None
        assert opp.missing_skills is not None
        assert opp.ai_scored_at is not None

    @pytest.mark.asyncio
    @patch("services.opportunity_scorer.scorer.generate_with_fallback")
    async def test_score_multiple_returns_sorted(self, mock_fallback) -> None:
        from services.ai import AIResponse

        async def side_effect(*args, **kwargs):
            return (
                AIResponse(
                    content='{"relevance_score": 75, "summary": "ok", '
                            '"pros": [], "cons": [], '
                            '"required_skills": [], "missing_skills": [], '
                            '"application_deadline": "", "ranking_explanation": ""}',
                    model="test-model",
                    provider="OpenRouter",
                ),
                "openrouter",
            )

        mock_fallback.side_effect = side_effect

        profile = Profile(id=uuid4(), user_id=uuid4(), skills=["Python"])
        now = datetime.now(timezone.utc)
        opps = [
            Opportunity(
                id=uuid4(), user_id=profile.user_id,
                title=f"Job {i}", description="desc",
                discovered_at=now,
            )
            for i in range(3)
        ]
        scorer = OpportunityScorer(provider_name="openrouter", model_name="test-model")
        results = await scorer.score_multiple_and_save(profile, opps)

        assert len(results) == 3
        scores = [r.relevance_score for r in results]
        assert scores == sorted(scores, reverse=True)

    @pytest.mark.asyncio
    @patch("services.opportunity_scorer.scorer.generate_with_fallback")
    async def test_score_with_full_profile(self, mock_fallback) -> None:
        from services.ai import AIResponse

        mock_fallback.return_value = (
            AIResponse(
                content='{"relevance_score": 92, "summary": "Excellent", '
                        '"pros": [], "cons": [], '
                        '"required_skills": [], "missing_skills": [], '
                        '"application_deadline": "", "ranking_explanation": ""}',
                model="test-model",
                provider="OpenRouter",
            ),
            "openrouter",
        )

        profile = Profile(
            id=uuid4(),
            user_id=uuid4(),
            display_name="Alice",
            bio="Experienced backend developer",
            skills=["Python", "FastAPI", "PostgreSQL", "Docker"],
            preferred_locations=["Remote", "New York"],
            salary_expectations="$150k+",
            target_companies=["Google", "Stripe"],
            keywords=["distributed systems", "microservices"],
            experience=[
                {"company": "TechCo", "role": "Senior Engineer"},
                {"company": "Startup", "role": "Backend Dev"},
            ],
            education=[
                {"degree": "BS", "field": "Computer Science", "institution": "MIT"},
            ],
        )
        scorer = OpportunityScorer(provider_name="openrouter", model_name="test-model")
        result = await scorer.score_opportunity(
            profile=profile,
            title="Senior Backend Engineer at Google",
            description="Design and build distributed systems",
        )
        assert result.title == "Senior Backend Engineer at Google"
        assert result.relevance_score == 92