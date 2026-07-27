"""Tests for RuleBasedQueryGenerator and the create_query_generator factory."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from uuid import uuid4

from database.models.profiles import Profile
from services.search_pipeline.steps.query_generator import (
    QueryGenerator,
    create_query_generator,
)
from services.search_pipeline.steps.query_generator_rules import (
    FALLBACK_QUERIES,
    RuleBasedQueryGenerator,
)


# ── fixtures ──────────────────────────────────────────────────────────


def _profile(
    skills: list[str] | None = None,
    roles: list[str] | None = None,
    locations: list[str] | None = None,
    companies: list[str] | None = None,
    keywords: list[str] | None = None,
    edu_fields: list[str] | None = None,
) -> Profile:
    p = Profile(id=uuid4(), user_id=uuid4())
    p.skills = skills
    if roles:
        p.experience = [{"role": r} for r in roles]
    else:
        p.experience = None
    p.preferred_locations = locations
    p.target_companies = companies
    p.keywords = keywords
    if edu_fields:
        p.education = [{"field": f} for f in edu_fields]
    else:
        p.education = None
    return p


@pytest.fixture
def empty_profile() -> Profile:
    return Profile(id=uuid4(), user_id=uuid4())


@pytest.fixture
def full_profile() -> Profile:
    return _profile(
        skills=["Python", "FastAPI", "Docker"],
        roles=["Software Engineer", "Backend Developer"],
        locations=["Bangalore", "Remote"],
        companies=["Google", "Stripe"],
        keywords=["machine learning", "distributed systems"],
        edu_fields=["Computer Science"],
    )


@pytest.fixture
def mock_plugin_keywords():
    """Patch load_bundled_plugins / get_plugin_keywords to return a known set."""
    fake_keywords = {
        "internships": ["internship", "intern", "graduate"],
        "jobs": ["job", "hiring", "position"],
    }
    with patch(
        "services.search_pipeline.steps.query_generator_rules.get_plugin_keywords",
        return_value=fake_keywords,
    ), patch(
        "services.search_pipeline.steps.query_generator_rules.load_bundled_plugins",
        return_value=[],
    ):
        yield


# ── candidate generation ─────────────────────────────────────────────


class TestGenerateCandidates:
    def test_full_profile(self, full_profile: Profile, mock_plugin_keywords) -> None:
        gen = RuleBasedQueryGenerator(query_count=10)
        candidates = gen._generate_candidates(full_profile, {
            "internships": ["internship", "intern", "graduate"],
            "jobs": ["job", "hiring", "position"],
        })
        assert len(candidates) > 0
        assert all(isinstance(c, str) and len(c) > 0 for c in candidates)

    def test_empty_profile(self, empty_profile: Profile, mock_plugin_keywords) -> None:
        gen = RuleBasedQueryGenerator(query_count=5)
        candidates = gen._generate_candidates(empty_profile, {})
        assert len(candidates) == 0

    def test_skills_only(self) -> None:
        p = _profile(skills=["Python", "Go"])
        gen = RuleBasedQueryGenerator(query_count=10)
        candidates = gen._generate_candidates(p, {})
        assert any("Python" in c for c in candidates)
        assert any("Go" in c for c in candidates)

    def test_roles_only(self) -> None:
        p = _profile(roles=["Engineer"])
        gen = RuleBasedQueryGenerator(query_count=10)
        candidates = gen._generate_candidates(p, {})
        assert any("Engineer" in c for c in candidates)

    def test_plugin_keywords_appear(self) -> None:
        p = _profile(skills=["Python"])
        gen = RuleBasedQueryGenerator(query_count=10)
        candidates = gen._generate_candidates(p, {
            "internships": ["internship", "graduate"],
        })
        assert any("internship" in c for c in candidates)
        assert any("graduate" in c for c in candidates)


# ── query selection (dedup + cap) ────────────────────────────────────


class TestSelectQueries:
    def test_dedup(self) -> None:
        gen = RuleBasedQueryGenerator(query_count=10)
        queries = gen._select_queries(["a", "b", "a", "c", "b", "c"])
        assert queries == ["a", "b", "c"]

    def test_cap(self) -> None:
        gen = RuleBasedQueryGenerator(query_count=3)
        queries = gen._select_queries(["a", "b", "c", "d", "e"])
        assert queries == ["a", "b", "c"]

    def test_under_cap_no_trim(self) -> None:
        gen = RuleBasedQueryGenerator(query_count=10)
        queries = gen._select_queries(["x", "y"])
        assert queries == ["x", "y"]

    def test_fallback_when_empty(self) -> None:
        gen = RuleBasedQueryGenerator(query_count=5)
        queries = gen._select_queries([])
        assert queries == list(FALLBACK_QUERIES)


# ── execute integration ──────────────────────────────────────────────


class TestExecute:
    async def test_sets_ctx_key(self, full_profile: Profile, mock_plugin_keywords) -> None:
        gen = RuleBasedQueryGenerator(query_count=5)
        ctx = {"profile": full_profile}
        result = await gen.execute(ctx)
        assert "queries" in result
        assert len(result["queries"]) > 0
        assert all(isinstance(q, str) and len(q) > 0 for q in result["queries"])

    async def test_no_profile_raises(self) -> None:
        gen = RuleBasedQueryGenerator(query_count=5)
        with pytest.raises(ValueError, match="No profile"):
            await gen.execute({"profile": None})

    async def test_plugin_keywords_in_output(self, mock_plugin_keywords) -> None:
        p = _profile(skills=["Python"])
        gen = RuleBasedQueryGenerator(query_count=10)
        ctx = {"profile": p}
        result = await gen.execute(ctx)
        text = " ".join(result["queries"]).lower()
        assert "internship" in text or "graduate" in text

    async def test_cap_honored(self, full_profile: Profile, mock_plugin_keywords) -> None:
        gen = RuleBasedQueryGenerator(query_count=3)
        ctx = {"profile": full_profile}
        result = await gen.execute(ctx)
        assert len(result["queries"]) <= 3

    async def test_fallback_on_empty_profile(self, empty_profile: Profile, mock_plugin_keywords) -> None:
        gen = RuleBasedQueryGenerator(query_count=5)
        ctx = {"profile": empty_profile}
        result = await gen.execute(ctx)
        assert result["queries"] == list(FALLBACK_QUERIES)

    async def test_ai_provider_used_is_rules(self, full_profile: Profile, mock_plugin_keywords) -> None:
        gen = RuleBasedQueryGenerator(query_count=5)
        ctx = {"profile": full_profile}
        result = await gen.execute(ctx)
        assert result.get("ai_provider_used") == "rules"


# ── factory ──────────────────────────────────────────────────────────


class TestCreateQueryGenerator:
    def test_default_backend_returns_rules(self) -> None:
        step = create_query_generator()
        assert isinstance(step, RuleBasedQueryGenerator)

    def test_llm_backend_returns_llm(self) -> None:
        with patch(
            "services.search_pipeline.steps.query_generator.get_config"
        ) as mock_cfg:
            mock_cfg.return_value.ai.query_generation.backend = "llm"
            step = create_query_generator(
                provider="openrouter",
                model="meta-llama/llama-3.3-70b-instruct:free",
            )
            assert isinstance(step, QueryGenerator)
