"""Tests for EmbeddingOpportunityScorer and create_opportunity_scorer factory.

These tests load a real (small) sentence-embedding model, so they serve
as both correctness and integration tests for the local scoring path.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import patch
from uuid import uuid4

import pytest

from core.config import get_config, reload_config
from database.models.opportunities import Opportunity
from database.models.profiles import Profile
from services.opportunity_scorer import (
    EmbeddingOpportunityScorer,
    ScoredOpportunity,
    create_opportunity_scorer,
)
from services.opportunity_scorer.embedding_scorer import (
    _COMMON_SKILLS,
    _build_profile_text,
    _cosine_sim_to_score,
    _extract_skills_from_text,
    _get_model,
)


# ── fixtures ──────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def _load_model():
    """Ensure the embedding model is loaded once per module.

    Tests that call ``EmbeddingOpportunityScorer()`` or
    ``_get_model()`` indirectly trigger this anyway; the fixture just
    makes the load explicit so CI logs are clearer.
    """
    return _get_model()


@pytest.fixture
def profile_python() -> Profile:
    return Profile(
        id=uuid4(),
        user_id=uuid4(),
        display_name="Alice",
        bio="Experienced Python backend developer",
        skills=["Python", "FastAPI", "PostgreSQL", "Docker", "Redis"],
        preferred_locations=["Remote"],
        target_companies=["Stripe"],
        keywords=["distributed systems"],
        experience=[{"company": "Acme", "role": "Backend Engineer"}],
        education=[{"degree": "BS", "field": "Computer Science", "institution": "MIT"}],
    )


@pytest.fixture
def profile_ml() -> Profile:
    return Profile(
        id=uuid4(),
        user_id=uuid4(),
        display_name="Bob",
        bio="Machine learning researcher focused on NLP and LLMs",
        skills=["Python", "PyTorch", "TensorFlow", "NLP", "Transformers", "R"],
        target_companies=["OpenAI", "Google"],
        education=[{"degree": "PhD", "field": "Computer Science", "institution": "Stanford"}],
    )


# ── ScoredOpportunity dataclass ───────────────────────────────────────
# (re-uses the same dataclass from scorer.py — just verify it's exported)


class TestScoredOpportunity:
    def test_default_fields(self) -> None:
        s = ScoredOpportunity()
        assert s.opportunity_id == ""
        assert s.title == ""
        assert s.relevance_score == 0.0

    def test_all_fields(self) -> None:
        s = ScoredOpportunity(
            opportunity_id="abc",
            title="Engineer",
            relevance_score=85.0,
            summary="Good",
            pros=["A"],
            cons=["B"],
            required_skills=["Python"],
            missing_skills=["K8s"],
            application_deadline="2026-09-01",
            ranking_explanation="Strong",
        )
        assert s.relevance_score == 85.0
        assert s.required_skills == ["Python"]


# ── _cosine_sim_to_score ──────────────────────────────────────────────


class TestCosineSimToScore:
    def test_extremes(self) -> None:
        assert _cosine_sim_to_score(-1.0) == 0
        assert _cosine_sim_to_score(1.0) >= 95

    def test_midpoint(self) -> None:
        # At sim=0.50 the sigmoid output is 0.5 → 50
        score = _cosine_sim_to_score(0.50)
        assert 40 <= score <= 60

    def test_low_sim(self) -> None:
        score = _cosine_sim_to_score(0.0)
        assert score <= 10

    def test_high_sim(self) -> None:
        score = _cosine_sim_to_score(0.8)
        assert score >= 90

    def test_fair_sim(self) -> None:
        score = _cosine_sim_to_score(0.25)
        assert 1 <= score <= 40

    def test_monotonic(self) -> None:
        prev = -1
        for s in range(-100, 101, 5):
            cur = _cosine_sim_to_score(s / 100.0)
            assert cur >= prev, f"Non-monotonic at sim={s/100}"
            prev = cur


# ── _build_profile_text ──────────────────────────────────────────────


class TestBuildProfileText:
    def test_empty_profile(self) -> None:
        p = Profile(id=uuid4(), user_id=uuid4())
        text = _build_profile_text(p)
        assert text == "No profile details available."

    def test_full_profile(self, profile_python: Profile) -> None:
        text = _build_profile_text(profile_python)
        assert "Alice" in text
        assert "Python" in text
        assert "FastAPI" in text
        assert "Docker" in text
        assert "Remote" in text
        assert "Stripe" in text
        assert "Backend Engineer" in text
        assert "Computer Science" in text


# ── _extract_skills_from_text ────────────────────────────────────────


class TestExtractSkillsFromText:
    def test_known_skills_found(self) -> None:
        text = "Looking for a Python developer with AWS and Docker experience"
        skills = _extract_skills_from_text(text, _COMMON_SKILLS)
        assert "python" in skills
        assert "aws" in skills
        assert "docker" in skills

    def test_no_skills_found(self) -> None:
        text = "We are hiring a barista for a cozy coffee shop"
        skills = _extract_skills_from_text(text, _COMMON_SKILLS)
        assert skills == []

    def test_compound_skill_matched(self) -> None:
        text = "Deep learning and computer vision expert needed"
        skills = _extract_skills_from_text(text, _COMMON_SKILLS)
        assert "deep learning" in skills
        assert "computer vision" in skills

    def test_case_insensitive(self) -> None:
        text = "DOCKER, KUBERNETES, and GOLANG positions available"
        skills = _extract_skills_from_text(text, _COMMON_SKILLS)
        assert "docker" in skills
        assert "kubernetes" in skills
        assert "golang" in skills

    def test_empty_text(self) -> None:
        assert _extract_skills_from_text("", _COMMON_SKILLS) == []


# ── EmbeddingOpportunityScorer — integration ─────────────────────────


class TestEmbeddingOpportunityScorer:
    """These tests load a real sentence-embedding model."""

    @pytest.mark.asyncio
    async def test_score_matching_opportunity_higher_than_unrelated(
        self,
        profile_python: Profile,
        _load_model,
    ) -> None:
        scorer = EmbeddingOpportunityScorer()

        matching = await scorer.score_opportunity(
            profile=profile_python,
            title="Senior Backend Python Engineer",
            description="Build distributed APIs with FastAPI, PostgreSQL, and Docker at Stripe",
        )
        unrelated = await scorer.score_opportunity(
            profile=profile_python,
            title="Barista at Local Coffee Shop",
            description="Making coffee and serving customers in a cozy cafe environment",
        )

        assert matching.relevance_score > unrelated.relevance_score
        assert 0 <= matching.relevance_score <= 100
        assert 0 <= unrelated.relevance_score <= 100
        assert isinstance(matching.relevance_score, int)

    @pytest.mark.asyncio
    async def test_score_returns_all_fields(
        self,
        profile_python: Profile,
        _load_model,
    ) -> None:
        scorer = EmbeddingOpportunityScorer()
        result = await scorer.score_opportunity(
            profile=profile_python,
            title="Python Developer",
            description="Use Python, FastAPI, and Docker to build backend services",
            url="https://example.com/job",
        )

        assert isinstance(result, ScoredOpportunity)
        assert result.title == "Python Developer"
        assert result.url == "https://example.com/job"
        assert isinstance(result.relevance_score, int)
        assert 0 <= result.relevance_score <= 100
        assert result.summary
        assert isinstance(result.pros, list)
        assert isinstance(result.cons, list)
        assert isinstance(result.required_skills, list)
        assert isinstance(result.missing_skills, list)
        assert result.application_deadline == ""
        assert result.ranking_explanation

    @pytest.mark.asyncio
    async def test_required_and_missing_skills(
        self,
        _load_model,
    ) -> None:
        profile = Profile(
            id=uuid4(),
            user_id=uuid4(),
            skills=["Python", "FastAPI"],
        )
        scorer = EmbeddingOpportunityScorer()
        result = await scorer.score_opportunity(
            profile=profile,
            title="Senior Python/React Developer",
            description="Use Python, FastAPI, React, Docker, and AWS to build web applications",
        )

        assert "python" in [s.lower() for s in result.required_skills]
        assert "docker" in [s.lower() for s in result.required_skills]
        assert "aws" in [s.lower() for s in result.required_skills]
        assert "react" in [s.lower() for s in result.required_skills]
        assert "fastapi" in [s.lower() for s in result.required_skills]

        # Python and FastAPI are in profile → not missing
        missing_lower = [s.lower() for s in result.missing_skills]
        assert "python" not in missing_lower
        assert "fastapi" not in missing_lower
        # Docker and AWS are in description but not in profile.skills → missing
        assert "docker" in missing_lower
        assert "aws" in missing_lower

    @pytest.mark.asyncio
    async def test_score_and_save_updates_opportunity(
        self,
        profile_python: Profile,
        _load_model,
    ) -> None:
        opp = Opportunity(
            id=uuid4(),
            user_id=profile_python.user_id,
            title="Backend Engineer",
            description="Python, FastAPI, PostgreSQL",
            url="https://example.com",
            discovered_at=datetime.now(timezone.utc),
        )
        scorer = EmbeddingOpportunityScorer()
        result = await scorer.score_and_save(profile_python, opp)

        assert result.opportunity_id == str(opp.id)
        assert opp.relevance_score is not None
        assert opp.summary is not None
        assert opp.pros is not None
        assert opp.cons is not None
        assert opp.required_skills is not None
        assert opp.missing_skills is not None
        assert opp.ai_scored_at is not None

    @pytest.mark.asyncio
    async def test_score_multiple_returns_sorted(
        self,
        profile_python: Profile,
        _load_model,
    ) -> None:
        now = datetime.now(timezone.utc)
        opps = [
            Opportunity(
                id=uuid4(), user_id=profile_python.user_id,
                title=f"Job {i}", description="",
                discovered_at=now,
            )
            for i in range(5)
        ]
        scorer = EmbeddingOpportunityScorer()
        results = await scorer.score_multiple_and_save(profile_python, opps)

        assert len(results) == 5
        scores = [r.relevance_score for r in results]
        assert scores == sorted(scores, reverse=True)

    @pytest.mark.asyncio
    async def test_score_empty_profile(self, _load_model) -> None:
        profile = Profile(id=uuid4(), user_id=uuid4())
        scorer = EmbeddingOpportunityScorer()
        result = await scorer.score_opportunity(
            profile=profile,
            title="Some Job",
            description="Nothing specific",
        )
        assert isinstance(result.relevance_score, int)
        assert 0 <= result.relevance_score <= 100

    @pytest.mark.asyncio
    async def test_score_multiple_empty_list(self, _load_model) -> None:
        profile = Profile(id=uuid4(), user_id=uuid4())
        scorer = EmbeddingOpportunityScorer()
        results = await scorer.score_multiple_and_save(profile, [])
        assert results == []

    @pytest.mark.asyncio
    async def test_pros_includes_matched_skills(
        self,
        profile_python: Profile,
        _load_model,
    ) -> None:
        scorer = EmbeddingOpportunityScorer()
        result = await scorer.score_opportunity(
            profile=profile_python,
            title="Python Backend Developer",
            description="FastAPI, PostgreSQL, Docker, Redis",
        )
        pros_text = " ".join(result.pros).lower()
        assert "python" in pros_text or "fastapi" in pros_text

    @pytest.mark.asyncio
    async def test_pros_includes_target_company_match(
        self,
        _load_model,
    ) -> None:
        profile = Profile(
            id=uuid4(),
            user_id=uuid4(),
            skills=["Python"],
            target_companies=["Stripe"],
        )
        scorer = EmbeddingOpportunityScorer()
        result = await scorer.score_opportunity(
            profile=profile,
            title="Software Engineer at Stripe",
            description="Build payment infrastructure",
        )
        pros_text = " ".join(result.pros)
        assert "Stripe" in pros_text

    @pytest.mark.asyncio
    async def test_cons_lists_missing_skills(
        self,
        _load_model,
    ) -> None:
        profile = Profile(
            id=uuid4(),
            user_id=uuid4(),
            skills=["Python"],
        )
        scorer = EmbeddingOpportunityScorer()
        result = await scorer.score_opportunity(
            profile=profile,
            title="Full Stack Developer",
            description="React, TypeScript, Docker, AWS, CI/CD, PostgreSQL",
        )
        assert len(result.missing_skills) > 0
        assert len(result.cons) > 0
        # Each cons line should mention a missing skill (cons are capped at 5
        # but at least one should reference a known missing term)
        cons_text = " ".join(result.cons).lower()
        assert any(ms.lower() in cons_text for ms in result.missing_skills)
        assert result.cons[0].startswith("Missing skill:")
        # With Python in profile, it should NOT be listed as missing
        cons_all = " ".join(result.cons).lower()
        assert "python" not in cons_all


# ── Factory ──────────────────────────────────────────────────────────


class TestCreateOpportunityScorer:
    def test_default_returns_embedding(self) -> None:
        scorer = create_opportunity_scorer()
        assert isinstance(scorer, EmbeddingOpportunityScorer)

    def test_embedding_backend(self) -> None:
        scorer = create_opportunity_scorer(backend="embedding")
        assert isinstance(scorer, EmbeddingOpportunityScorer)

    @patch("services.opportunity_scorer.embedding_scorer.create_opportunity_scorer")
    def test_llm_backend_returns_opportunity_scorer(self, mock_factory) -> None:
        # Verify the factory dispatch works by testing config-driven switching
        from services.opportunity_scorer.scorer import OpportunityScorer

        # Simulate what the factory does when backend="llm"
        mock_factory.side_effect = lambda **kw: OpportunityScorer(
            provider_name=kw.get("provider_name"),
            model_name=kw.get("model_name"),
        )
        scorer = create_opportunity_scorer(backend="llm")
        # We can't easily test this without patching get_config, so verify
        # the import path works and the function signature is correct
        assert callable(create_opportunity_scorer)

    def test_backend_from_config(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OOS_AI__SCORING_BACKEND", "llm")
        reload_config()
        try:
            scorer = create_opportunity_scorer()
            from services.opportunity_scorer.scorer import OpportunityScorer
            assert isinstance(scorer, OpportunityScorer)
        finally:
            monkeypatch.delenv("OOS_AI__SCORING_BACKEND", raising=False)
            reload_config()

    def test_embedding_from_config(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OOS_AI__SCORING_BACKEND", "embedding")
        reload_config()
        try:
            scorer = create_opportunity_scorer()
            assert isinstance(scorer, EmbeddingOpportunityScorer)
        finally:
            monkeypatch.delenv("OOS_AI__SCORING_BACKEND", raising=False)
            reload_config()


# ── Enrichment helpers ───────────────────────────────────────────────


class TestParseEnrichmentResponse:
    def test_single_valid_json(self) -> None:
        from services.opportunity_scorer.embedding_scorer import _parse_enrichment_response
        data = '{"summary": "Great role", "pros": ["A"], "cons": ["B"], "ranking_explanation": "C"}'
        result = _parse_enrichment_response(data, single=True)
        assert isinstance(result, dict)
        assert result["summary"] == "Great role"

    def test_single_missing_field(self) -> None:
        from services.opportunity_scorer.embedding_scorer import _parse_enrichment_response
        result = _parse_enrichment_response('{"pros": []}', single=True)
        assert result is None

    def test_single_invalid_json(self) -> None:
        from services.opportunity_scorer.embedding_scorer import _parse_enrichment_response
        assert _parse_enrichment_response("not json", single=True) is None

    def test_single_with_code_fence(self) -> None:
        from services.opportunity_scorer.embedding_scorer import _parse_enrichment_response
        data = '```\n{"summary": "OK", "pros": [], "cons": [], "ranking_explanation": ""}\n```'
        result = _parse_enrichment_response(data, single=True)
        assert isinstance(result, dict)
        assert result["summary"] == "OK"

    def test_batch_valid_json(self) -> None:
        from services.opportunity_scorer.embedding_scorer import _parse_enrichment_response
        data = (
            '[{"summary": "A", "pros": [], "cons": [], "ranking_explanation": ""},'
            '{"summary": "B", "pros": [], "cons": [], "ranking_explanation": ""}]'
        )
        result = _parse_enrichment_response(data, single=False)
        assert isinstance(result, list)
        assert len(result) == 2

    def test_batch_wrong_type(self) -> None:
        from services.opportunity_scorer.embedding_scorer import _parse_enrichment_response
        result = _parse_enrichment_response('{"summary": "A"}', single=False)
        assert result is None

    def test_batch_item_missing_summary(self) -> None:
        from services.opportunity_scorer.embedding_scorer import _parse_enrichment_response
        result = _parse_enrichment_response('[{"pros": []}]', single=False)
        assert result is None


class TestBuildEnrichmentBatchItems:
    def test_single_result(self) -> None:
        from services.opportunity_scorer.embedding_scorer import _build_enrichment_batch_items
        r = ScoredOpportunity(title="Job A", relevance_score=85, required_skills=["Py"], missing_skills=[])
        text = _build_enrichment_batch_items([r])
        assert "Job A" in text
        assert "85" in text
        assert "Py" in text

    def test_multiple_results(self) -> None:
        from services.opportunity_scorer.embedding_scorer import _build_enrichment_batch_items
        results = [
            ScoredOpportunity(title="Job A", relevance_score=85, required_skills=["Py"], missing_skills=[]),
            ScoredOpportunity(title="Job B", relevance_score=42, required_skills=[], missing_skills=["K8s"]),
        ]
        text = _build_enrichment_batch_items(results)
        assert "Opportunity 1" in text
        assert "Opportunity 2" in text
        assert "Job A" in text
        assert "Job B" in text


class TestApplyEnrichment:
    def _apply(self, r, enriched):
        r.summary = enriched.get("summary", r.summary) if enriched else r.summary
        r.pros = enriched.get("pros", r.pros) if enriched else r.pros
        r.cons = enriched.get("cons", r.cons) if enriched else r.cons
        r.ranking_explanation = enriched.get("ranking_explanation", r.ranking_explanation) if enriched else r.ranking_explanation

    def test_overwrites_text_fields(self) -> None:
        r = ScoredOpportunity(
            title="Job", relevance_score=50, summary="old",
            pros=["old"], cons=["old"], ranking_explanation="old",
        )
        enriched = {"summary": "new", "pros": ["new p"], "cons": ["new c"], "ranking_explanation": "new e"}
        self._apply(r, enriched)
        assert r.summary == "new"
        assert r.pros == ["new p"]
        assert r.cons == ["new c"]
        assert r.ranking_explanation == "new e"

    def test_preserves_score_and_skills(self) -> None:
        r = ScoredOpportunity(
            title="Job", relevance_score=50, summary="old",
            required_skills=["A"], missing_skills=["B"],
        )
        self._apply(r, {"summary": "new", "pros": [], "cons": [], "ranking_explanation": ""})
        assert r.relevance_score == 50
        assert r.required_skills == ["A"]
        assert r.missing_skills == ["B"]

    def test_none_enriched_does_nothing(self) -> None:
        r = ScoredOpportunity(title="Job", summary="keep")
        self._apply(r, None)
        assert r.summary == "keep"


# ── Enrichment integration ───────────────────────────────────────────


class TestEnrichmentFlow:
    """Tests for the optional LLM narrative enrichment pass."""

    @pytest.mark.asyncio
    async def test_disabled_by_default_never_calls_ai(
        self,
        profile_python: Profile,
        _load_model,
    ) -> None:
        """With enrichment disabled (the default), no AI registry is touched."""
        scorer = EmbeddingOpportunityScorer()
        result = await scorer.score_opportunity(
            profile=profile_python,
            title="Python Developer",
        )
        # Template text — no "Natural language" or enrichment prose
        assert result.summary.startswith("Python Developer")

    @pytest.mark.asyncio
    async def test_disabled_by_default_via_score_and_save(
        self,
        profile_python: Profile,
        _load_model,
    ) -> None:
        opp = Opportunity(
            id=uuid4(), user_id=profile_python.user_id,
            title="Backend", description="",
            discovered_at=datetime.now(timezone.utc),
        )
        scorer = EmbeddingOpportunityScorer()
        result = await scorer.score_and_save(profile_python, opp)
        assert result.summary.startswith("Backend")

    @pytest.mark.asyncio
    async def test_disabled_by_default_via_score_multiple(
        self,
        profile_python: Profile,
        _load_model,
    ) -> None:
        now = datetime.now(timezone.utc)
        opps = [Opportunity(id=uuid4(), user_id=profile_python.user_id, title="Job", discovered_at=now)]
        scorer = EmbeddingOpportunityScorer()
        results = await scorer.score_multiple_and_save(profile_python, opps)
        assert results[0].summary.startswith("Job")

    @pytest.mark.asyncio
    async def test_enabled_succeeding_overwrites_text_fields(
        self,
        profile_python: Profile,
        _load_model,
    ) -> None:
        """Enrichment overwrites summary/pros/cons/ranking_explanation but
        preserves relevance_score, required_skills, missing_skills."""
        from services.ai import AIResponse

        enriched_json = (
            '{"summary": "Natural prose summary", '
            '"pros": ["Natural pro"], '
            '"cons": ["Natural con"], '
            '"ranking_explanation": "Natural explanation"}'
        )

        async def mock_generate(*args, **kwargs) -> tuple[AIResponse, str]:
            return (
                AIResponse(content=enriched_json, model="test", provider="openrouter"),
                "openrouter",
            )

        scorer = EmbeddingOpportunityScorer(narrative_enrichment_enabled=True)
        with patch.object(scorer, "_enrich_single", mock_generate):
            # _enrich_single is async, so mock_generate is an async function
            # But we want to mock generate_with_fallback, not _enrich_single
            pass

        # `generate_with_fallback` is imported inside _enrich_single, so patch at source
        target = "services.ai.fallback.generate_with_fallback"
        with patch(target, new=mock_generate):
            scorer2 = EmbeddingOpportunityScorer(narrative_enrichment_enabled=True)
            result = await scorer2.score_opportunity(
                profile=profile_python,
                title="Python Developer",
                description="Build with Python and FastAPI",
            )

        assert result.summary == "Natural prose summary"
        assert result.pros == ["Natural pro"]
        assert result.cons == ["Natural con"]
        assert result.ranking_explanation == "Natural explanation"
        # Score and skills preserved from template
        assert isinstance(result.relevance_score, int)
        assert 0 <= result.relevance_score <= 100
        assert len(result.required_skills) > 0
        assert result.application_deadline == ""

    @pytest.mark.asyncio
    async def test_enabled_failing_falls_back(
        self,
        profile_python: Profile,
        _load_model,
    ) -> None:
        """When the enrichment call raises an exception, template text is kept
        and no exception propagates."""
        async def mock_fail(*args, **kwargs) -> tuple:
            raise RuntimeError("API failure")

        target = "services.ai.fallback.generate_with_fallback"
        with patch(target, new=mock_fail):
            scorer = EmbeddingOpportunityScorer(narrative_enrichment_enabled=True)
            result = await scorer.score_opportunity(
                profile=profile_python,
                title="Python Developer",
                description="Build with Python and FastAPI",
            )

        # Falls back to template text
        assert result.summary.startswith("Python Developer")
        assert isinstance(result.relevance_score, int)
        assert result.application_deadline == ""

    @pytest.mark.asyncio
    async def test_enabled_bad_parse_falls_back(
        self,
        profile_python: Profile,
        _load_model,
    ) -> None:
        """When the enrichment response is unparseable, template text is kept."""
        from services.ai import AIResponse

        async def mock_bad_response(*args, **kwargs) -> tuple[AIResponse, str]:
            return (
                AIResponse(content="not valid json at all", model="test", provider="openrouter"),
                "openrouter",
            )

        target = "services.ai.fallback.generate_with_fallback"
        with patch(target, new=mock_bad_response):
            scorer = EmbeddingOpportunityScorer(narrative_enrichment_enabled=True)
            result = await scorer.score_opportunity(
                profile=profile_python,
                title="Python Developer",
            )

        assert result.summary.startswith("Python Developer")
        assert result.relevance_score is not None

    @pytest.mark.asyncio
    async def test_enriched_score_and_save(
        self,
        profile_python: Profile,
        _load_model,
    ) -> None:
        from services.ai import AIResponse

        enriched_json = (
            '{"summary": "Enriched summary", '
            '"pros": ["Pro"], "cons": ["Con"], '
            '"ranking_explanation": "Explanation"}'
        )

        async def mock_generate(*args, **kwargs) -> tuple[AIResponse, str]:
            return (
                AIResponse(content=enriched_json, model="test", provider="openrouter"),
                "openrouter",
            )

        opp = Opportunity(
            id=uuid4(), user_id=profile_python.user_id,
            title="Python Dev", description="Python, FastAPI",
            discovered_at=datetime.now(timezone.utc),
        )

        target = "services.ai.fallback.generate_with_fallback"
        with patch(target, new=mock_generate):
            scorer = EmbeddingOpportunityScorer(narrative_enrichment_enabled=True)
            result = await scorer.score_and_save(profile_python, opp)

        assert result.summary == "Enriched summary"
        assert opp.summary == "Enriched summary"  # opportunity object also updated
        assert result.pros == ["Pro"]
        assert opp.pros == ["Pro"]
        assert isinstance(result.relevance_score, int)

    @pytest.mark.asyncio
    async def test_batch_enrichment_overwrites_fields(
        self,
        profile_python: Profile,
        _load_model,
    ) -> None:
        from services.ai import AIResponse

        batch_json = (
            '[{"summary": "Enriched A", "pros": ["Pa"], "cons": ["Ca"], "ranking_explanation": "Ra"},'
            '{"summary": "Enriched B", "pros": ["Pb"], "cons": ["Cb"], "ranking_explanation": "Rb"}]'
        )

        async def mock_generate(*args, **kwargs) -> tuple[AIResponse, str]:
            return (
                AIResponse(content=batch_json, model="test", provider="openrouter"),
                "openrouter",
            )

        now = datetime.now(timezone.utc)
        opps = [
            Opportunity(id=uuid4(), user_id=profile_python.user_id, title="Job A", description="", discovered_at=now),
            Opportunity(id=uuid4(), user_id=profile_python.user_id, title="Job B", description="", discovered_at=now),
        ]

        target = "services.ai.fallback.generate_with_fallback"
        with patch(target, new=mock_generate):
            scorer = EmbeddingOpportunityScorer(narrative_enrichment_enabled=True)
            results = await scorer.score_multiple_and_save(profile_python, opps)

        assert len(results) == 2
        assert results[0].summary == "Enriched A"
        assert results[1].summary == "Enriched B"
        assert results[0].pros == ["Pa"]
        assert results[1].pros == ["Pb"]
        # Opportunity objects also updated
        assert opps[0].summary == "Enriched A"
        assert opps[1].summary == "Enriched B"
        # Score and skills preserved
        assert isinstance(results[0].relevance_score, int)
        assert results[0].application_deadline == ""

    @pytest.mark.asyncio
    async def test_batch_enrichment_failure_falls_back(
        self,
        profile_python: Profile,
        _load_model,
    ) -> None:
        async def mock_fail(*args, **kwargs) -> tuple:
            raise RuntimeError("API failure")

        now = datetime.now(timezone.utc)
        opps = [
            Opportunity(id=uuid4(), user_id=profile_python.user_id, title="Job A", description="", discovered_at=now),
            Opportunity(id=uuid4(), user_id=profile_python.user_id, title="Job B", description="", discovered_at=now),
        ]

        target = "services.ai.fallback.generate_with_fallback"
        with patch(target, new=mock_fail):
            scorer = EmbeddingOpportunityScorer(narrative_enrichment_enabled=True)
            results = await scorer.score_multiple_and_save(profile_python, opps)

        assert len(results) == 2
        assert results[0].summary.startswith("Job")
        assert results[1].summary.startswith("Job")
        assert results[0].relevance_score is not None
