"""Embedding-based opportunity scorer — no AI provider calls by default.

Uses a local sentence-embedding model (all-MiniLM-L6-v2 via
sentence-transformers) for relevance scoring and rule-based logic for
skill matching, pros/cons, and explanation text.

When ``cfg.ai.narrative_enrichment_enabled`` is ``True``, an optional
LLM enrichment pass rewrites the template-generated text fields into
more natural prose — one call per opportunity (``score_opportunity``) or
batched (``score_multiple_and_save``).  The LLM never re-derives the
score or skills; it only rephrases already-computed facts.  If the
enrichment call fails, template text is kept and no exception propagates.
"""

from __future__ import annotations

import asyncio
import json
import logging
import math
from datetime import datetime, timezone
from typing import Any

from database.models.opportunities import Opportunity
from database.models.profiles import Profile
from services.opportunity_scorer.scorer import ScoredOpportunity

logger = logging.getLogger(__name__)

# ── static skill vocabulary (case-insensitive matching) ──────────────

_COMMON_SKILLS: frozenset[str] = frozenset({
    # Programming languages
    "python", "javascript", "typescript", "java", "c++", "c#", "go",
    "golang", "rust", "kotlin", "swift", "ruby", "php", "scala", "r",
    "matlab", "dart", "lua", "perl", "haskell", "elixir", "clojure",
    "sql", "assembly", "bash", "powershell",
    # Web frameworks
    "react", "angular", "vue", "svelte", "django", "flask", "fastapi",
    "express", "spring boot", "spring", "asp.net", "rails", "laravel",
    "next.js", "nuxt.js", "jquery", "bootstrap", "tailwind", "redux",
    "graphql", "rest api", "restful", "webpack", "vite",
    # Databases
    "postgresql", "postgres", "mysql", "sqlite", "mongodb", "redis",
    "elasticsearch", "cassandra", "dynamodb", "mariadb", "oracle",
    "mssql", "sql server", "neo4j", "couchdb", "firebase", "supabase",
    # Cloud / DevOps
    "aws", "azure", "gcp", "google cloud", "docker", "kubernetes", "k8s",
    "terraform", "ansible", "pulumi", "jenkins", "circleci", "travis ci",
    "github actions", "gitlab ci", "ci/cd", "helm", "prometheus",
    "grafana", "datadog", "new relic", "splunk",
    # ML / AI / Data
    "machine learning", "deep learning", "nlp", "natural language processing",
    "computer vision", "reinforcement learning", "llm", "large language model",
    "generative ai", "rag", "fine-tuning", "prompt engineering",
    "tensorflow", "pytorch", "scikit-learn", "keras", "xgboost",
    "lightgbm", "hugging face", "spacy", "nltk", "opencv",
    "data analysis", "data science", "data engineering", "data pipeline",
    "apache spark", "spark", "hadoop", "kafka", "airflow", "dbt",
    "pandas", "numpy", "scipy", "tableau", "power bi", "looker",
    "statistics", "probability", "regression", "classification",
    "clustering", "a/b testing", "experimental design",
    # Tools & Platforms
    "git", "linux", "unix", "vim", "vscode", "visual studio code",
    "jira", "confluence", "postman", "swagger", "figma", "sketch",
    "adobe xd", "photoshop", "illustrator", "blender", "unity", "unreal",
    "nginx", "apache", "rabbitmq", "celery", "grpc", "websocket",
    # Domains
    "backend", "back-end", "frontend", "front-end", "full stack",
    "full-stack", "mobile", "ios", "android", "react native", "flutter",
    "devops", "sre", "site reliability", "security", "cybersecurity",
    "qa", "quality assurance", "testing", "sdet", "automation",
    "embedded systems", "iot", "internet of things", "firmware",
    "game development", "game design", "ar/vr", "blockchain",
    # Soft skills
    "leadership", "communication", "teamwork", "collaboration",
    "project management", "agile", "scrum", "kanban", "problem solving",
    "critical thinking", "mentoring", "time management", "adaptability",
    # Business & domain
    "product management", "product strategy", "user research", "ux",
    "ui design", "marketing", "digital marketing", "seo", "sem",
    "sales", "business development", "consulting", "strategy",
    "operations", "supply chain", "logistics", "finance", "accounting",
    "hrm", "human resources", "recruiting", "talent acquisition",
    # Research & science
    "scientific computing", "research methodology", "literature review",
    "data collection", "signal processing", "image processing",
    "bioinformatics", "computational biology", "chemistry",
    "physics", "mathematics", "econometrics", "psychometrics",
    # Hardware & engineering
    "arduino", "raspberry pi", "pcb design", "fpga", "vlsi",
    "verilog", "vhdl", "rtos", "microcontroller", "sensor",
    "cad", "solidworks", "autocad", "matlab simulink",
})

_EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"
_MODEL: Any = None


def _get_model():
    global _MODEL
    if _MODEL is None:
        from sentence_transformers import SentenceTransformer
        _MODEL = SentenceTransformer(_EMBEDDING_MODEL_NAME)
    return _MODEL


def _build_profile_text(profile: Profile) -> str:
    # When raw_extracted_text is available, prefer it as the primary source
    # for the richest semantic signal. Append structured fields as supplement.
    raw = getattr(profile, "raw_extracted_text", None)
    if raw and raw.strip():
        parts: list[str] = [raw.strip()]
    else:
        parts = []

    if profile.display_name:
        parts.append(f"Name: {profile.display_name}")
    if profile.bio:
        parts.append(f"Bio: {profile.bio}")
    if profile.skills:
        parts.append(f"Skills: {', '.join(profile.skills)}")
    if profile.preferred_locations:
        parts.append(f"Locations: {', '.join(profile.preferred_locations)}")
    if profile.salary_expectations:
        parts.append(f"Salary: {profile.salary_expectations}")
    if profile.target_companies:
        parts.append(f"Target Companies: {', '.join(profile.target_companies)}")
    if profile.keywords:
        parts.append(f"Keywords: {', '.join(profile.keywords)}")
    if profile.experience:
        roles = [e.get("role", "") for e in profile.experience if e.get("role")]
        if roles:
            parts.append(f"Past Roles: {', '.join(roles)}")
    if profile.education:
        fields = [e.get("field", "") for e in profile.education if e.get("field")]
        if fields:
            parts.append(f"Education Fields: {', '.join(fields)}")
    if not parts:
        return "No profile details available."
    return " | ".join(parts)


def _build_opportunity_text(title: str, description: str | None = None) -> str:
    text = title
    if description:
        text = f"{text} | {description}"
    return text


def _cosine_sim_to_score(sim: float) -> int:
    # Center sigmoid at 0.5 (require genuine semantic similarity for high scores)
    # Slope of 8 gives a gradual curve — scores below 0.3 stay low, above 0.7 climb fast
    calibrated = 1.0 / (1.0 + math.exp(-8.0 * (sim - 0.50)))
    # Floor: if cosine similarity is below 0.1, cap score at 5 (near-zero match)
    raw = calibrated * 100.0
    if sim < 0.10:
        raw = min(raw, 5.0)
    return int(round(max(0.0, min(100.0, raw))))


def _extract_skills_from_text(text: str, vocab: frozenset[str]) -> list[str]:
    lower = text.lower()
    found: set[str] = set()
    for term in vocab:
        if len(term) < 2:
            continue
        if term.lower() in lower:
            found.add(term)
    return sorted(found)


def _extract_required_and_missing(
    title: str,
    description: str | None,
    profile_skills: list[str] | None,
    vocab: frozenset[str],
) -> tuple[list[str], list[str]]:
    combined = f"{title} {description or ''}"
    required = _extract_skills_from_text(combined, vocab)

    profile_skills_lower = {s.lower().strip() for s in (profile_skills or [])}
    missing = [s for s in required if s.lower() not in profile_skills_lower]

    return required, missing


def _generate_template_fields(
    title: str,
    score: int,
    required_skills: list[str],
    missing_skills: list[str],
    matched_profile_skills: set[str],
    matched_companies: set[str],
) -> tuple[str, list[str], list[str], str]:
    summary = (
        f"{title} — {score}% relevance, "
        f"{len(required_skills)} skill{'s' if len(required_skills) != 1 else ''} identified, "
        f"{len(matched_profile_skills)} of your skills apply."
    )

    pros: list[str] = []
    if matched_profile_skills:
        pros.append(f"Your skills that match: {', '.join(sorted(matched_profile_skills))}")
    if matched_companies:
        pros.append(f"Target company match: {', '.join(sorted(matched_companies))}")
    if score >= 70:
        pros.append("High overall relevance score")
    if not pros:
        pros.append("Some alignment with your profile")

    cons: list[str] = []
    for ms in missing_skills[:5]:
        cons.append(f"Missing skill: {ms}")
    if not cons:
        cons.append("No significant skill gaps detected")

    ranking_explanation = (
        f"Embedding-based relevance score: {score}/100 derived from "
        f"semantic similarity between your profile and this opportunity. "
        f"{len(required_skills)} skill{'s' if len(required_skills) != 1 else ''} matched, "
        f"{len(missing_skills)} skill{'s' if len(missing_skills) != 1 else ''} missing."
    )

    return summary, pros, cons, ranking_explanation


# ── enrichment prompts ───────────────────────────────────────────────

_ENRICHMENT_SYSTEM_PROMPT = (
    "You are an assistant that writes natural opportunity-scoring descriptions. "
    "The facts below have already been computed correctly. "
    "Do NOT change the score or skills. "
    "Only rewrite the summary, pros, cons, and ranking_explanation into more natural, "
    "human-readable prose. Return ONLY valid JSON."
)

_ENRICHMENT_USER_TEMPLATE_SINGLE = """Opportunity Title: {title}
Description: {description}
Relevance Score (already correct): {score}/100
Required Skills (already correct): {required_skills}
Missing Skills (already correct): {missing_skills}

Return ONLY valid JSON with these exact fields:
{{
  "summary": "natural 1-2 sentence summary",
  "pros": ["pro 1", "pro 2"],
  "cons": ["con 1", "con 2"],
  "ranking_explanation": "brief natural explanation"
}}"""

_ENRICHMENT_USER_TEMPLATE_BATCH = """The facts below have already been computed correctly for each opportunity. Do NOT change the score or skills. Only rewrite the summary, pros, cons, and ranking_explanation into more natural, human-readable prose for each.

{items_block}

Return ONLY a valid JSON array. Each element must have exactly these fields:
{{"summary": "...", "pros": [...], "cons": [...], "ranking_explanation": "..."}}"""


def _build_enrichment_batch_items(results: list[ScoredOpportunity]) -> str:
    lines: list[str] = []
    for i, r in enumerate(results, 1):
        lines.append(f"Opportunity {i}:")
        lines.append(f"  Title: {r.title}")
        lines.append(f"  Score: {r.relevance_score}/100")
        lines.append(f"  Required Skills: {r.required_skills}")
        lines.append(f"  Missing Skills: {r.missing_skills}")
        lines.append("")
    return "\n".join(lines).strip()


def _parse_enrichment_response(
    content: str,
    single: bool,
) -> list[dict[str, Any]] | dict[str, Any] | None:
    content = content.strip()
    if content.startswith("```"):
        content = content.split("\n", 1)[-1]
        content = content.rsplit("```", 1)[0]
    content = content.strip()
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        return None
    if single:
        if isinstance(parsed, dict) and "summary" in parsed:
            return parsed
        return None
    if isinstance(parsed, list) and all(isinstance(i, dict) and "summary" in i for i in parsed):
        return parsed
    return None


# ── scorer ───────────────────────────────────────────────────────────


class EmbeddingOpportunityScorer:
    """Scores opportunities using local embeddings and rule-based logic.

    Public interface mirrors ``OpportunityScorer`` in ``scorer.py`` so
    the two are drop-in replacements governed by ``cfg.ai.scoring_backend``.

    When ``narrative_enrichment_enabled`` is ``True``, an optional LLM
    pass rewrites text fields into more natural prose.  The enrichment is
    non-authoritative — if the LLM call fails the template text is kept.
    """

    def __init__(self, narrative_enrichment_enabled: bool | None = None) -> None:
        self._model = _get_model()
        self._enrichment_enabled = narrative_enrichment_enabled
        if self._enrichment_enabled is None:
            from core.config import get_config
            cfg = get_config()
            self._enrichment_enabled = cfg.ai.narrative_enrichment_enabled

    async def _enrich_single(
        self,
        result: ScoredOpportunity,
        title: str,
        description: str | None,
    ) -> dict[str, Any] | None:
        """One LLM call to rewrite text fields for a single opportunity.

        Returns a dict with ``summary``, ``pros``, ``cons``,
        ``ranking_explanation`` or ``None`` on failure.
        """
        from core.config import get_config
        from services.ai import AIRegistry, ModelConfig
        from services.ai.fallback import generate_with_fallback

        cfg = get_config()
        try:
            user_prompt = _ENRICHMENT_USER_TEMPLATE_SINGLE.format(
                title=title,
                description=description or "",
                score=int(result.relevance_score),
                required_skills=json.dumps(result.required_skills),
                missing_skills=json.dumps(result.missing_skills),
            )
            config = ModelConfig(
                model=cfg.ai.default_model,
                temperature=0.5,
                max_tokens=1024,
            )
            messages = [
                {"role": "system", "content": _ENRICHMENT_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ]
            registry = AIRegistry.default()
            response, _used_provider = await generate_with_fallback(
                registry=registry,
                primary_provider=cfg.ai.default_provider,
                messages=messages,
                config=config,
                fallback_providers=cfg.ai.fallback_providers,
            )
            parsed = _parse_enrichment_response(response.content, single=True)
            if not isinstance(parsed, dict):
                logger.warning("Enrichment response parse failed for '%s'", title)
                return None
            return parsed
        except Exception as exc:
            logger.warning("Enrichment call failed for '%s': %s", title, exc)
            return None

    async def _enrich_batch(
        self,
        results: list[ScoredOpportunity],
    ) -> list[dict[str, Any]] | None:
        """One batched LLM call to rewrite text fields for multiple results.

        Falls back to per-item ``_enrich_single`` if the batch response
        cannot be parsed or when there is only one result.
        """
        if not results:
            return None

        if len(results) == 1:
            enriched = await self._enrich_single(results[0], results[0].title, None)
            return [enriched] if enriched else None

        from core.config import get_config
        from services.ai import AIRegistry, ModelConfig
        from services.ai.fallback import generate_with_fallback

        cfg = get_config()
        try:
            items_block = _build_enrichment_batch_items(results)
            user_prompt = _ENRICHMENT_USER_TEMPLATE_BATCH.format(items_block=items_block)
            config = ModelConfig(
                model=cfg.ai.default_model,
                temperature=0.5,
                max_tokens=2048,
            )
            messages = [
                {"role": "system", "content": _ENRICHMENT_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ]
            registry = AIRegistry.default()
            response, _used_provider = await generate_with_fallback(
                registry=registry,
                primary_provider=cfg.ai.default_provider,
                messages=messages,
                config=config,
                fallback_providers=cfg.ai.fallback_providers,
            )
            parsed_list = _parse_enrichment_response(response.content, single=False)
            if not isinstance(parsed_list, list) or len(parsed_list) != len(results):
                logger.warning(
                    "Batch enrichment parse failed: expected %d items, got %r",
                    len(results),
                    type(parsed_list),
                )
                return None
            return parsed_list
        except Exception as exc:
            logger.warning("Batch enrichment call failed for %d items: %s", len(results), exc)
            return None

    def _apply_enrichment(
        self,
        result: ScoredOpportunity,
        enriched: dict[str, Any] | None,
    ) -> None:
        """Overwrite text fields on *result* with enriched values if available."""
        if not enriched:
            return
        result.summary = enriched.get("summary", result.summary)
        result.pros = enriched.get("pros", result.pros)
        result.cons = enriched.get("cons", result.cons)
        result.ranking_explanation = enriched.get("ranking_explanation", result.ranking_explanation)

    # ── public API ───────────────────────────────────────────────────

    async def score_opportunity(
        self,
        profile: Profile,
        title: str,
        description: str | None = None,
        url: str | None = None,
    ) -> ScoredOpportunity:
        result = await self._compute_score(profile, title, description, url)

        if self._enrichment_enabled:
            enriched = await self._enrich_single(result, title, description)
            self._apply_enrichment(result, enriched)

        return result

    async def score_and_save(
        self,
        profile: Profile,
        opportunity: Opportunity,
    ) -> ScoredOpportunity:
        result = await self._compute_score(
            profile,
            opportunity.title,
            opportunity.description,
            opportunity.url,
        )
        result.opportunity_id = str(opportunity.id)

        opportunity.relevance_score = result.relevance_score
        opportunity.summary = result.summary
        opportunity.pros = result.pros
        opportunity.cons = result.cons
        opportunity.required_skills = result.required_skills
        opportunity.missing_skills = result.missing_skills
        opportunity.application_deadline = result.application_deadline
        opportunity.ranking_explanation = result.ranking_explanation
        opportunity.ai_scored_at = datetime.now(timezone.utc)

        if self._enrichment_enabled:
            enriched = await self._enrich_single(result, opportunity.title, opportunity.description)
            if enriched:
                self._apply_enrichment(result, enriched)
                opportunity.summary = result.summary
                opportunity.pros = result.pros
                opportunity.cons = result.cons
                opportunity.ranking_explanation = result.ranking_explanation

        return result

    async def score_multiple_and_save(
        self,
        profile: Profile,
        opportunities: list[Opportunity],
        max_concurrent: int = 5,
    ) -> list[ScoredOpportunity]:
        sem = asyncio.Semaphore(max_concurrent)
        opp_results: list[tuple[ScoredOpportunity, Opportunity]] = []

        async def _scored(opp: Opportunity) -> tuple[ScoredOpportunity, Opportunity]:
            async with sem:
                result = await self._compute_score(
                    profile, opp.title, opp.description, opp.url,
                )
                result.opportunity_id = str(opp.id)

                opp.relevance_score = result.relevance_score
                opp.summary = result.summary
                opp.pros = result.pros
                opp.cons = result.cons
                opp.required_skills = result.required_skills
                opp.missing_skills = result.missing_skills
                opp.application_deadline = result.application_deadline
                opp.ranking_explanation = result.ranking_explanation
                opp.ai_scored_at = datetime.now(timezone.utc)

                return result, opp

        tasks = [_scored(opp) for opp in opportunities]
        opp_results = await asyncio.gather(*tasks)
        results = [r for r, _ in opp_results]
        results.sort(key=lambda r: r.relevance_score, reverse=True)

        if self._enrichment_enabled and results:
            enriched_list = await self._enrich_batch(results)
            if enriched_list:
                for i, r in enumerate(enriched_list[:len(results)]):
                    self._apply_enrichment(results[i], r)
                    opp = opp_results[i][1]
                    opp.summary = results[i].summary
                    opp.pros = results[i].pros
                    opp.cons = results[i].cons
                    opp.ranking_explanation = results[i].ranking_explanation

        return results

    async def _compute_score(
        self,
        profile: Profile,
        title: str,
        description: str | None = None,
        url: str | None = None,
    ) -> ScoredOpportunity:
        """Template-based scoring only — no enrichment."""
        profile_text = _build_profile_text(profile)
        opp_text = _build_opportunity_text(title, description)

        emb_profile = self._model.encode([profile_text], normalize_embeddings=True)[0]
        emb_opp = self._model.encode([opp_text], normalize_embeddings=True)[0]

        cosine_sim = float(emb_profile @ emb_opp)
        relevance_score = _cosine_sim_to_score(cosine_sim)

        required_skills, missing_skills = _extract_required_and_missing(
            title=title,
            description=description,
            profile_skills=profile.skills,
            vocab=_COMMON_SKILLS,
        )

        profile_skills_lower = {s.lower().strip() for s in (profile.skills or [])}
        matched_profile_skills = {
            s for s in required_skills if s.lower() in profile_skills_lower
        }
        matched_companies = set()
        if profile.target_companies:
            lower_title = (title or "").lower()
            for company in profile.target_companies:
                if company.lower() in lower_title:
                    matched_companies.add(company)

        summary, pros, cons, ranking_explanation = _generate_template_fields(
            title=title,
            score=relevance_score,
            required_skills=required_skills,
            missing_skills=missing_skills,
            matched_profile_skills=matched_profile_skills,
            matched_companies=matched_companies,
        )

        return ScoredOpportunity(
            opportunity_id="",
            title=title,
            url=url or "",
            relevance_score=relevance_score,
            summary=summary,
            pros=pros,
            cons=cons,
            required_skills=required_skills,
            missing_skills=missing_skills,
            application_deadline="",
            ranking_explanation=ranking_explanation,
        )


def create_opportunity_scorer(
    backend: str | None = None,
    provider_name: str | None = None,
    model_name: str | None = None,
) -> Any:
    """Factory: return an EmbeddingOpportunityScorer or OpportunityScorer.

    Reads ``cfg.ai.scoring_backend`` — if ``"embedding"`` (the default)
    returns an ``EmbeddingOpportunityScorer``; if ``"llm"`` returns the
    original LLM-based ``OpportunityScorer`` with optional provider/model
    override.
    """
    from core.config import get_config

    cfg = get_config()
    scoring_backend = backend or cfg.ai.scoring_backend

    if scoring_backend == "llm":
        from services.opportunity_scorer.scorer import OpportunityScorer

        return OpportunityScorer(
            provider_name=provider_name,
            model_name=model_name,
        )

    return EmbeddingOpportunityScorer()
