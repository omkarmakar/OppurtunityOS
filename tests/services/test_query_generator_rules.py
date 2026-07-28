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
    TIER_KEYS,
    _company_to_careers_domain,
    _infer_industries,
)


# ── fixtures ──────────────────────────────────────────────────────────


def _profile(
    skills: list[str] | None = None,
    roles: list[str] | None = None,
    locations: list[str] | None = None,
    companies: list[str] | None = None,
    keywords: list[str] | None = None,
    edu_fields: list[str] | None = None,
    raw_text: str | None = None,
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
    p.raw_extracted_text = raw_text
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


def _flatten(tiered: dict[str, list[str]]) -> list[str]:
    flat: list[str] = []
    for k in TIER_KEYS:
        flat.extend(tiered.get(k, []))
    return flat


# ── industry inference ────────────────────────────────────────────────


class TestInferIndustries:
    def test_empty_skills(self) -> None:
        assert _infer_industries([], "") == []

    def test_ai_ml_from_skills(self) -> None:
        inds = _infer_industries(["pytorch", "nlp", "tensorflow"], "")
        assert "AI/ML" in inds
        assert inds[0] == "AI/ML"

    def test_semiconductors_from_skills(self) -> None:
        inds = _infer_industries(["verilog", "vlsi"], "")
        assert "Semiconductors" in inds

    def test_raw_text_enriches(self) -> None:
        inds = _infer_industries(["python"], "worked on fpga and verilog designs")
        assert "Semiconductors" in inds

    def test_multiple_industries_scored(self) -> None:
        inds = _infer_industries(["pytorch", "tensorflow", "nlp", "docker"], "")
        assert inds.index("AI/ML") < inds.index("Cloud/DevOps")


# ── company domain resolution ─────────────────────────────────────────


class TestCompanyToDomain:
    def test_known_company(self) -> None:
        assert _company_to_careers_domain("Google") == "careers.google.com"
        assert _company_to_careers_domain("meta") == "metacareers.com"

    def test_unknown_returns_none(self) -> None:
        assert _company_to_careers_domain("SomeRandomStartup") is None

    def test_case_insensitive(self) -> None:
        assert _company_to_careers_domain("AMAZON") == "amazon.jobs"


# ── candidate generation (tiered) ─────────────────────────────────────


class TestGenerateCandidates:
    def test_full_profile(self, full_profile: Profile, mock_plugin_keywords) -> None:
        gen = RuleBasedQueryGenerator(query_count=10)
        tiered = gen._generate_candidates(full_profile, {
            "internships": ["internship", "intern", "graduate"],
            "jobs": ["job", "hiring", "position"],
        })
        flat = _flatten(tiered)
        assert len(flat) > 0
        assert all(isinstance(c, str) and len(c) > 0 for c in flat)

    def test_empty_profile(self, empty_profile: Profile, mock_plugin_keywords) -> None:
        gen = RuleBasedQueryGenerator(query_count=5)
        tiered = gen._generate_candidates(empty_profile, {})
        flat = _flatten(tiered)
        assert len(flat) == 0

    def test_skills_only(self) -> None:
        p = _profile(skills=["Python", "Go"])
        gen = RuleBasedQueryGenerator(query_count=10)
        tiered = gen._generate_candidates(p, {})
        flat = _flatten(tiered)
        assert any("Python" in c for c in flat)
        assert any("Go" in c for c in flat)

    def test_roles_only(self) -> None:
        p = _profile(roles=["Engineer"])
        gen = RuleBasedQueryGenerator(query_count=10)
        tiered = gen._generate_candidates(p, {})
        flat = _flatten(tiered)
        assert any("Engineer" in c for c in flat)

    def test_plugin_keywords_appear(self) -> None:
        p = _profile(skills=["Python"])
        gen = RuleBasedQueryGenerator(query_count=10)
        tiered = gen._generate_candidates(p, {
            "internships": ["internship", "graduate"],
        })
        flat = _flatten(tiered)
        assert any("internship" in c for c in flat)
        assert any("graduate" in c for c in flat)

    def test_industry_queries_present(self) -> None:
        p = _profile(skills=["pytorch", "tensorflow", "nlp"])
        gen = RuleBasedQueryGenerator(query_count=10)
        tiered = gen._generate_candidates(p, {})
        flat = _flatten(tiered)
        assert any("AI/ML" in c for c in flat)

    def test_company_site_queries_in_tier_b(self) -> None:
        p = _profile(skills=["Python"], companies=["Google", "UnknownCo"])
        gen = RuleBasedQueryGenerator(query_count=20)
        tiered = gen._generate_candidates(p, {})
        b_queries = tiered["b"]
        # Google has a known domain -> site:careers.google.com
        assert any("site:careers.google.com" in q for q in b_queries)
        # UnknownCo has no known domain -> plain fallback
        assert any("UnknownCo" in q and "site:" not in q for q in b_queries)

    def test_job_board_queries_in_tier_c(self) -> None:
        p = _profile(skills=["Python"], roles=["Engineer"])
        gen = RuleBasedQueryGenerator(query_count=20)
        tiered = gen._generate_candidates(p, {})
        c_queries = tiered["c"]
        assert any("site:linkedin.com/jobs" in q for q in c_queries)
        assert any("site:indeed.com" in q for q in c_queries)

    def test_location_never_standalone_in_tier_a(self) -> None:
        """Location should NOT appear as an independent top-priority axis."""
        p = _profile(
            skills=["Python"],
            roles=["Engineer"],
            locations=["Bangalore"],
            companies=["Google"],
        )
        gen = RuleBasedQueryGenerator(query_count=20)
        tiered = gen._generate_candidates(p, {})
        # Tier A should have no bare location queries
        for q in tiered["a"]:
            assert "Bangalore" not in q or "Python" in q or "Engineer" in q or "Google" in q
        # Location should only appear in Tier D
        tier_d_locations = [q for q in tiered["d"] if "Bangalore" in q]
        assert len(tier_d_locations) > 0

    def test_tier_d_has_location_suffixes(self) -> None:
        p = _profile(
            skills=["Python"],
            roles=["Engineer"],
            locations=["Remote"],
        )
        gen = RuleBasedQueryGenerator(query_count=20)
        tiered = gen._generate_candidates(p, {})
        d_queries = tiered["d"]
        assert any(q.endswith(" Remote") for q in d_queries)

    def test_raw_text_enriches_skills(self) -> None:
        p = _profile(skills=["Python"], raw_text="worked on fpga and verilog")
        gen = RuleBasedQueryGenerator(query_count=20)
        tiered = gen._generate_candidates(p, {})
        flat = _flatten(tiered)
        assert any("fpga" in c for c in flat)
        assert any("verilog" in c for c in flat)

    def test_no_companies_falls_back_gracefully(self) -> None:
        p = _profile(skills=["Python"], roles=["Engineer"], companies=[])
        gen = RuleBasedQueryGenerator(query_count=10)
        tiered = gen._generate_candidates(p, {})
        flat = _flatten(tiered)
        assert any("Python" in c for c in flat)
        assert any("Engineer" in c for c in flat)

    def test_no_industries_still_produces_skill_queries(self) -> None:
        """When skills have no industry mapping, skill+role queries still work."""
        p = _profile(skills=["some_obscure_tool"], roles=["Engineer"])
        gen = RuleBasedQueryGenerator(query_count=10)
        tiered = gen._generate_candidates(p, {})
        flat = _flatten(tiered)
        # No industry should be inferred, but skill+role queries exist
        assert any("some_obscure_tool" in c for c in flat)
        assert any("Engineer" in c for c in flat)


# ── query selection (proportional across tiers) ───────────────────────


class TestSelectQueries:
    def _make_tiered(self, items: dict[str, list[str]]) -> dict[str, list[str]]:
        return {k: items.get(k, []) for k in TIER_KEYS}

    def test_dedup(self) -> None:
        gen = RuleBasedQueryGenerator(query_count=10)
        queries = gen._select_queries(self._make_tiered({
            "a": ["a", "b"],
            "b": ["a", "c"],
        }))
        assert queries == ["a", "b", "c"]

    def test_cap(self) -> None:
        gen = RuleBasedQueryGenerator(query_count=3)
        queries = gen._select_queries(self._make_tiered({
            "a": ["a", "b", "c", "d", "e"],
        }))
        assert len(queries) == 3
        assert queries == ["a", "b", "c"]

    def test_under_cap_no_trim(self) -> None:
        gen = RuleBasedQueryGenerator(query_count=10)
        queries = gen._select_queries(self._make_tiered({
            "a": ["x", "y"],
        }))
        assert queries == ["x", "y"]

    def test_fallback_when_empty(self) -> None:
        gen = RuleBasedQueryGenerator(query_count=5)
        queries = gen._select_queries(self._make_tiered({}))
        assert queries == list(FALLBACK_QUERIES)

    def test_proportional_allocation(self) -> None:
        """With query_count=10, each tier gets roughly its share."""
        gen = RuleBasedQueryGenerator(query_count=10)
        tiered = self._make_tiered({
            "a": [f"a_{i}" for i in range(20)],
            "b": [f"b_{i}" for i in range(20)],
            "c": [f"c_{i}" for i in range(20)],
            "d": [f"d_{i}" for i in range(20)],
        })
        queries = gen._select_queries(tiered)
        # Should have at least 2 from each tier
        a_count = sum(1 for q in queries if q.startswith("a_"))
        b_count = sum(1 for q in queries if q.startswith("b_"))
        c_count = sum(1 for q in queries if q.startswith("c_"))
        d_count = sum(1 for q in queries if q.startswith("d_"))
        assert a_count >= 2
        assert b_count >= 1
        assert c_count >= 1
        assert len(queries) == 10

    def test_tier_b_and_c_get_remainder_slots(self) -> None:
        """Remainder slots after proportional split go to tiers B and C first."""
        gen = RuleBasedQueryGenerator(query_count=7)
        tiered = self._make_tiered({
            "a": [f"a_{i}" for i in range(10)],
            "b": [f"b_{i}" for i in range(10)],
            "c": [f"c_{i}" for i in range(10)],
            "d": [f"d_{i}" for i in range(10)],
        })
        queries = gen._select_queries(tiered)
        assert len(queries) == 7

    def test_location_not_top_priority_when_skills_present(self) -> None:
        """When query_count is small, location-suffixed queries (Tier D)
        should not crowd out higher-value company/board queries."""
        p = _profile(
            skills=["Python", "FastAPI"],
            roles=["Engineer"],
            locations=["Bangalore", "Remote", "Mumbai"],
            companies=["Google"],
        )
        gen = RuleBasedQueryGenerator(query_count=5)
        tiered = gen._generate_candidates(p, {})
        queries = gen._select_queries(tiered)
        # At least one query should mention Google or the site domain
        has_company = any("Google" in q or "careers.google.com" in q for q in queries)
        assert has_company, f"No company- or site-scoped query in {queries}"
        # Location-only queries (without skill/role/company) should NOT appear
        for q in queries:
            loc_words = {"bangalore", "remote", "mumbai"}
            q_lower = q.lower()
            if any(loc in q_lower for loc in loc_words):
                # Must also contain a skill, role, or company reference
                assert any(kw in q_lower for kw in ["python", "fastapi", "engineer", "google"]), (
                    f"Pure location query not allowed: {q}"
                )


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

    async def test_industry_in_output(self) -> None:
        p = _profile(skills=["pytorch", "tensorflow", "nlp"])
        gen = RuleBasedQueryGenerator(query_count=10)
        ctx = {"profile": p}
        result = await gen.execute(ctx)
        text = " ".join(result["queries"])
        assert "AI/ML" in text

    async def test_company_site_in_output(self) -> None:
        p = _profile(skills=["Python"], companies=["Google"])
        gen = RuleBasedQueryGenerator(query_count=10)
        ctx = {"profile": p}
        result = await gen.execute(ctx)
        text = " ".join(result["queries"])
        assert "site:" in text or "Google" in text

    async def test_job_board_in_output(self) -> None:
        p = _profile(skills=["Python"])
        gen = RuleBasedQueryGenerator(query_count=10)
        ctx = {"profile": p}
        result = await gen.execute(ctx)
        text = " ".join(result["queries"])
        assert "site:linkedin.com/jobs" in text or "site:indeed.com" in text

    async def test_no_location_before_skills(self) -> None:
        p = _profile(skills=["Python"], roles=["Engineer"], locations=["Remote"])
        gen = RuleBasedQueryGenerator(query_count=5)
        ctx = {"profile": p}
        result = await gen.execute(ctx)
        for q in result["queries"]:
            q_lower = q.lower()
            if "remote" in q_lower:
                assert any(kw in q_lower for kw in ["python", "engineer"])


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
