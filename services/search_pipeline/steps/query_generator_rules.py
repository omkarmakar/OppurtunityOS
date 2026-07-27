"""Pipeline step — generates search queries from profile data using templates.

Replaces the LLM-based QueryGenerator with a zero-cost rule-based backend
that constructs query strings directly from structured profile fields and
bundled plugin keyword sets.  No AI provider is called.
"""

from __future__ import annotations

import re
from typing import Any

from plugins.loader import get_plugin_keywords, load_bundled_plugins
from services.search_pipeline.steps.base import PipelineStep

# Shared skill vocabulary for extracting skills from raw text.
_COMMON_SKILLS: frozenset[str] = frozenset({
    "python", "javascript", "typescript", "java", "c++", "c#", "go",
    "golang", "rust", "kotlin", "swift", "ruby", "php", "scala", "r",
    "matlab", "dart", "lua", "perl", "haskell", "elixir", "clojure",
    "sql", "assembly", "bash", "powershell",
    "react", "angular", "vue", "svelte", "django", "flask", "fastapi",
    "express", "spring boot", "spring", "asp.net", "rails", "laravel",
    "next.js", "nuxt.js", "jquery", "bootstrap", "tailwind", "redux",
    "graphql", "rest api", "restful", "webpack", "vite",
    "postgresql", "postgres", "mysql", "sqlite", "mongodb", "redis",
    "elasticsearch", "cassandra", "dynamodb", "mariadb", "oracle",
    "mssql", "sql server", "neo4j", "couchdb", "firebase", "supabase",
    "aws", "azure", "gcp", "google cloud", "docker", "kubernetes", "k8s",
    "terraform", "ansible", "pulumi", "jenkins", "circleci", "travis ci",
    "github actions", "gitlab ci", "ci/cd", "helm", "prometheus",
    "grafana", "datadog", "new relic", "splunk",
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
    "git", "linux", "unix", "vim", "vscode", "visual studio code",
    "jira", "confluence", "postman", "swagger", "figma", "sketch",
    "adobe xd", "photoshop", "illustrator", "blender", "unity", "unreal",
    "nginx", "apache", "rabbitmq", "celery", "grpc", "websocket",
    "backend", "back-end", "frontend", "front-end", "full stack",
    "full-stack", "mobile", "ios", "android", "react native", "flutter",
    "devops", "sre", "site reliability", "security", "cybersecurity",
    "qa", "quality assurance", "testing", "sdet", "automation",
    "embedded systems", "iot", "internet of things", "firmware",
    "game development", "game design", "ar/vr", "blockchain",
    "leadership", "communication", "teamwork", "collaboration",
    "project management", "agile", "scrum", "kanban", "problem solving",
    "critical thinking", "mentoring", "time management", "adaptability",
    "product management", "product strategy", "user research", "ux",
    "ui design", "marketing", "digital marketing", "seo", "sem",
    "sales", "business development", "consulting", "strategy",
    "operations", "supply chain", "logistics", "finance", "accounting",
    "hrm", "human resources", "recruiting", "talent acquisition",
    "scientific computing", "research methodology", "literature review",
    "data collection", "signal processing", "image processing",
    "bioinformatics", "computational biology", "chemistry",
    "physics", "mathematics", "econometrics", "psychometrics",
    "arduino", "raspberry pi", "pcb design", "fpga", "vlsi",
    "verilog", "vhdl", "rtos", "microcontroller", "sensor",
    "cad", "solidworks", "autocad", "matlab simulink",
    "remote", "hybrid", "on-site", "onsite",
})


def _extract_skills_from_text(text: str, vocab: frozenset[str]) -> list[str]:
    lower = text.lower()
    found: set[str] = set()
    for term in vocab:
        if len(term) < 2:
            continue
        if term.lower() in lower:
            found.add(term)
    return sorted(found)

FALLBACK_QUERIES = ["entry level jobs", "junior positions", "graduate opportunities"]


class RuleBasedQueryGenerator(PipelineStep):
    """Generate search queries from profile fields via template expansion.

    Combines the profile's skills, experience roles, preferred locations,
    target companies, profile keywords, and education fields with each
    enabled plugin's domain-specific keyword set to produce a diverse
    query list — no AI call required.
    """

    def __init__(
        self,
        query_count: int = 5,
        enabled_plugins: list[str] | None = None,
    ) -> None:
        self._query_count = max(1, min(query_count, 20))
        self._enabled_plugins = enabled_plugins

    @property
    def name(self) -> str:
        return "QueryGenerator"

    async def execute(self, ctx: dict[str, Any]) -> dict[str, Any]:
        profile = ctx.get("profile")
        if not profile:
            raise ValueError("No profile found in context")

        plugin_keywords = self._load_plugin_keywords()

        candidates = self._generate_candidates(profile, plugin_keywords)
        queries = self._select_queries(candidates)

        ctx["queries"] = queries
        ctx["ai_provider_used"] = "rules"
        return ctx

    def _load_plugin_keywords(self) -> dict[str, list[str]]:
        plugins = load_bundled_plugins(self._enabled_plugins)
        return get_plugin_keywords(plugins)

    def _generate_candidates(
        self,
        profile: Any,
        plugin_keywords: dict[str, list[str]],
    ) -> list[str]:
        candidates: list[str] = []

        # When raw_extracted_text is present, extract additional skills/keywords
        # from the full resume text to supplement structured fields.
        raw_text = getattr(profile, "raw_extracted_text", None) or ""

        skills: list[str] = list(profile.skills or [])
        roles: list[str] = [e.get("role", "") for e in (profile.experience or []) if e.get("role")]
        locations: list[str] = list(profile.preferred_locations or [])
        companies: list[str] = list(profile.target_companies or [])
        profile_keywords: list[str] = list(profile.keywords or [])
        edu_fields: list[str] = [e.get("field", "") for e in (profile.education or []) if e.get("field")]

        if raw_text.strip():
            extracted = _extract_skills_from_text(raw_text, _COMMON_SKILLS)
            for s in extracted:
                if s not in skills:
                    skills.append(s)
            remote_pref = getattr(profile, "remote_preference", None)
            if remote_pref and remote_pref not in locations:
                locations.append(remote_pref)

        # ── skill-based templates ────────────────────────────────────
        for skill in skills:
            candidates.append(f"{skill} jobs")
            for role in roles:
                candidates.append(f"{skill} {role}")
                for loc in locations:
                    candidates.append(f"{skill} {role} {loc}")
            for loc in locations:
                candidates.append(f"{skill} jobs {loc}")
            for company in companies:
                candidates.append(f"{skill} {company}")
            for field in edu_fields:
                candidates.append(f"{skill} {field}")

        # ── role-based templates ─────────────────────────────────────
        for role in roles:
            candidates.append(f"{role} jobs")
            for loc in locations:
                candidates.append(f"{role} {loc}")
            for company in companies:
                candidates.append(f"{role} {company}")

        # ── company-based templates ──────────────────────────────────
        for company in companies:
            candidates.append(f"{company} hiring")
            for skill in skills:
                candidates.append(f"{skill} {company}")

        # ── education field templates ────────────────────────────────
        for field in edu_fields:
            candidates.append(f"{field} jobs")
            for loc in locations:
                candidates.append(f"{field} {loc}")

        # ── profile keyword templates ────────────────────────────────
        for kw in profile_keywords:
            candidates.append(kw)
            for skill in skills:
                candidates.append(f"{skill} {kw}")

        # ── plugin-category templates ────────────────────────────────
        for _plugin_name, keywords in plugin_keywords.items():
            for kw in keywords:
                for skill in skills:
                    candidates.append(f"{skill} {kw}")
                for role in roles:
                    candidates.append(f"{role} {kw}")
                for loc in locations:
                    candidates.append(f"{kw} {loc}")

        return candidates

    def _select_queries(self, candidates: list[str]) -> list[str]:
        seen: set[str] = set()
        deduped: list[str] = []
        for c in candidates:
            normal = c.lower().strip()
            if normal and normal not in seen:
                seen.add(normal)
                deduped.append(c.strip())

        if not deduped:
            return list(FALLBACK_QUERIES)

        if len(deduped) <= self._query_count:
            return deduped

        return deduped[:self._query_count]
