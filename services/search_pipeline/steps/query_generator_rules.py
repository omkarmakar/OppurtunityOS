"""Pipeline step — generates search queries from profile data using templates.

Replaces the LLM-based QueryGenerator with a zero-cost rule-based backend
that constructs query strings directly from structured profile fields and
bundled plugin keyword sets.  No AI provider is called.

Query tiering (in priority order):
  (a) skill/role/industry combined queries (no location)
  (b) target_company-site queries (site:domain or plain fallback)
  (c) job-board-site queries (via configurable job_boards list)
  (d) location suffix appended to a subset of top candidates from (a)-(c)
"""

from __future__ import annotations

import re
from collections import OrderedDict
from typing import Any

from core.config import get_config
from plugins.loader import get_plugin_keywords, load_bundled_plugins
from services.search_pipeline.steps.base import PipelineStep

# ── skill vocabulary ───────────────────────────────────────────────────

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

# ── skill-to-industry taxonomy ─────────────────────────────────────────

SKILL_TO_INDUSTRY: dict[str, list[str]] = {
    "pytorch": ["AI/ML"],
    "tensorflow": ["AI/ML"],
    "nlp": ["AI/ML"],
    "natural language processing": ["AI/ML"],
    "computer vision": ["AI/ML"],
    "deep learning": ["AI/ML"],
    "machine learning": ["AI/ML"],
    "llm": ["AI/ML"],
    "large language model": ["AI/ML"],
    "generative ai": ["AI/ML"],
    "rag": ["AI/ML"],
    "hugging face": ["AI/ML"],
    "spacy": ["AI/ML"],
    "scikit-learn": ["AI/ML", "Data Science"],
    "keras": ["AI/ML"],
    "xgboost": ["AI/ML", "Data Science"],
    "opencv": ["AI/ML", "Robotics"],
    "data science": ["Data Science", "AI/ML"],
    "data analysis": ["Data Science"],
    "data engineering": ["Data Engineering"],
    "data pipeline": ["Data Engineering"],
    "apache spark": ["Data Engineering"],
    "spark": ["Data Engineering"],
    "hadoop": ["Data Engineering"],
    "kafka": ["Data Engineering", "Backend"],
    "airflow": ["Data Engineering"],
    "dbt": ["Data Engineering"],
    "tableau": ["Data Science"],
    "power bi": ["Data Science"],
    "looker": ["Data Science"],
    "statistics": ["Data Science"],
    "react": ["Frontend"],
    "angular": ["Frontend"],
    "vue": ["Frontend"],
    "svelte": ["Frontend"],
    "django": ["Backend"],
    "flask": ["Backend"],
    "fastapi": ["Backend"],
    "express": ["Backend"],
    "spring boot": ["Backend"],
    "spring": ["Backend"],
    "asp.net": ["Backend"],
    "rails": ["Backend"],
    "laravel": ["Backend"],
    "next.js": ["Frontend", "Full Stack"],
    "redux": ["Frontend"],
    "graphql": ["Backend", "Full Stack"],
    "rest api": ["Backend"],
    "postgresql": ["Backend", "Data Engineering"],
    "postgres": ["Backend", "Data Engineering"],
    "mysql": ["Backend", "Data Engineering"],
    "mongodb": ["Backend", "Data Engineering"],
    "redis": ["Backend", "Data Engineering"],
    "elasticsearch": ["Data Engineering", "Backend"],
    "cassandra": ["Data Engineering"],
    "dynamodb": ["Data Engineering"],
    "aws": ["Cloud/DevOps"],
    "azure": ["Cloud/DevOps"],
    "gcp": ["Cloud/DevOps"],
    "google cloud": ["Cloud/DevOps"],
    "docker": ["Cloud/DevOps"],
    "kubernetes": ["Cloud/DevOps"],
    "terraform": ["Cloud/DevOps"],
    "ansible": ["Cloud/DevOps"],
    "pulumi": ["Cloud/DevOps"],
    "jenkins": ["Cloud/DevOps"],
    "circleci": ["Cloud/DevOps"],
    "github actions": ["Cloud/DevOps"],
    "gitlab ci": ["Cloud/DevOps"],
    "ci/cd": ["Cloud/DevOps"],
    "helm": ["Cloud/DevOps"],
    "prometheus": ["Cloud/DevOps", "SRE"],
    "grafana": ["Cloud/DevOps", "SRE"],
    "devops": ["Cloud/DevOps"],
    "sre": ["SRE", "Cloud/DevOps"],
    "site reliability": ["SRE", "Cloud/DevOps"],
    "security": ["Cybersecurity"],
    "cybersecurity": ["Cybersecurity"],
    "qa": ["QA/Testing"],
    "quality assurance": ["QA/Testing"],
    "testing": ["QA/Testing"],
    "sdet": ["QA/Testing"],
    "automation": ["QA/Testing", "Cloud/DevOps"],
    "embedded systems": ["Embedded Systems"],
    "iot": ["Embedded Systems"],
    "internet of things": ["Embedded Systems"],
    "firmware": ["Embedded Systems"],
    "arduino": ["Embedded Systems", "Hardware"],
    "raspberry pi": ["Embedded Systems", "Hardware"],
    "pcb design": ["Hardware"],
    "fpga": ["Semiconductors", "Hardware"],
    "vlsi": ["Semiconductors"],
    "verilog": ["Semiconductors"],
    "vhdl": ["Semiconductors"],
    "rtos": ["Embedded Systems"],
    "microcontroller": ["Embedded Systems", "Hardware"],
    "sensor": ["Embedded Systems", "IoT", "Hardware"],
    "cad": ["Hardware"],
    "solidworks": ["Hardware"],
    "autocad": ["Hardware"],
    "matlab": ["Research", "AI/ML"],
    "matlab simulink": ["Research", "AI/ML", "Hardware"],
    "r": ["Data Science", "Research"],
    "mobile": ["Mobile"],
    "ios": ["Mobile"],
    "android": ["Mobile"],
    "react native": ["Mobile", "Frontend"],
    "flutter": ["Mobile", "Frontend"],
    "unity": ["Game Development"],
    "unreal": ["Game Development"],
    "game development": ["Game Development"],
    "game design": ["Game Development"],
    "blockchain": ["Blockchain"],
    "product management": ["Product Management"],
    "product strategy": ["Product Management"],
    "user research": ["UX Research"],
    "ux": ["UX/Design"],
    "ui design": ["UX/Design"],
    "figma": ["UX/Design"],
    "marketing": ["Marketing"],
    "digital marketing": ["Marketing"],
    "seo": ["Marketing"],
    "sem": ["Marketing"],
    "sales": ["Sales"],
    "business development": ["Business Development"],
    "consulting": ["Consulting"],
    "strategy": ["Strategy"],
    "operations": ["Operations"],
    "supply chain": ["Supply Chain"],
    "logistics": ["Supply Chain"],
    "finance": ["Finance"],
    "accounting": ["Finance"],
    "hrm": ["HR"],
    "human resources": ["HR"],
    "recruiting": ["HR", "Talent Acquisition"],
    "talent acquisition": ["Talent Acquisition"],
    "bioinformatics": ["Life Sciences", "AI/ML"],
    "computational biology": ["Life Sciences", "AI/ML"],
    "chemistry": ["Life Sciences"],
    "physics": ["Research"],
    "mathematics": ["Research", "Data Science"],
    "signal processing": ["Hardware", "AI/ML"],
    "image processing": ["Computer Vision", "AI/ML"],
    "scientific computing": ["Research", "HPC"],
    "backend": ["Backend"],
    "frontend": ["Frontend"],
    "full stack": ["Full Stack"],
    "full-stack": ["Full Stack"],
}

# ── known company careers domains ──────────────────────────────────────

_KNOWN_COMPANY_DOMAINS: dict[str, str] = {
    "google": "careers.google.com",
    "microsoft": "careers.microsoft.com",
    "meta": "metacareers.com",
    "facebook": "metacareers.com",
    "amazon": "amazon.jobs",
    "apple": "apple.com/careers",
    "netflix": "jobs.netflix.com",
    "stripe": "stripe.com/jobs",
    "spotify": "spotify.com/jobs",
    "uber": "uber.com/careers",
    "airbnb": "airbnb.com/careers",
    "linkedin": "linkedin.com/jobs",
    "salesforce": "salesforce.com/careers",
    "oracle": "oracle.com/careers",
    "ibm": "ibm.com/careers",
    "intel": "intel.com/careers",
    "nvidia": "nvidia.com/careers",
    "amd": "amd.com/careers",
    "qualcomm": "qualcomm.com/careers",
    "tesla": "tesla.com/careers",
    "databricks": "databricks.com/careers",
    "snowflake": "snowflake.com/careers",
    "palantir": "palantir.com/careers",
    "github": "github.com/careers",
    "gitlab": "gitlab.com/jobs",
    "datadog": "datadoghq.com/careers",
    "cloudflare": "cloudflare.com/careers",
    "vercel": "vercel.com/careers",
    "confluent": "confluent.io/careers",
    "hashicorp": "hashicorp.com/careers",
    "red hat": "redhat.com/jobs",
    "canonical": "canonical.com/careers",
    "docker": "docker.com/careers",
    "slack": "slack.com/careers",
    "atlassian": "atlassian.com/careers",
    "coinbase": "coinbase.com/careers",
    "square": "squareup.com/careers",
    "pinterest": "pinterest.com/careers",
    "doordash": "doordash.com/careers",
    "lyft": "lyft.com/careers",
    "twilio": "twilio.com/jobs",
    "adobe": "adobe.com/careers",
    "cisco": "cisco.com/careers",
    "vmware": "vmware.com/careers",
    "dell": "dell.com/careers",
}

FALLBACK_QUERIES = ["entry level jobs", "junior positions", "graduate opportunities"]

TIER_KEYS = ["a", "b", "c", "d"]
TIER_PROPORTIONS = {"a": 0.40, "b": 0.25, "c": 0.25, "d": 0.10}


# ── helpers ────────────────────────────────────────────────────────────


def _extract_skills_from_text(text: str, vocab: frozenset[str]) -> list[str]:
    lower = text.lower()
    found: set[str] = set()
    for term in vocab:
        if len(term) < 2:
            continue
        if term.lower() in lower:
            found.add(term)
    return sorted(found)


def _infer_industries(skills: list[str], raw_text: str) -> list[str]:
    texts = " ".join(skills).lower()
    if raw_text:
        texts += " " + raw_text.lower()
    scores: dict[str, int] = {}
    for term, industries in SKILL_TO_INDUSTRY.items():
        if term in texts:
            for ind in industries:
                scores[ind] = scores.get(ind, 0) + 1
    sorted_inds = sorted(scores.items(), key=lambda x: -x[1])
    return [ind for ind, _ in sorted_inds]


def _company_to_careers_domain(company: str) -> str | None:
    key = company.lower().strip()
    if key in _KNOWN_COMPANY_DOMAINS:
        return _KNOWN_COMPANY_DOMAINS[key]
    slug = re.sub(r"[^a-z0-9]+", "", key)
    if slug and len(slug) >= 2:
        return None
    return None


# ── generator step ─────────────────────────────────────────────────────


class RuleBasedQueryGenerator(PipelineStep):
    """Generate search queries from profile data via template expansion.

    Queries are constructed in four priority tiers (see module docstring)
    and selected proportionally from each tier up to *query_count*.
    """

    def __init__(
        self,
        query_count: int = 5,
        enabled_plugins: list[str] | None = None,
    ) -> None:
        self._query_count = max(1, min(query_count, 20))
        self._enabled_plugins = enabled_plugins
        cfg = get_config()
        self._job_boards = cfg.ai.query_generation.job_boards

    @property
    def name(self) -> str:
        return "QueryGenerator"

    async def execute(self, ctx: dict[str, Any]) -> dict[str, Any]:
        profile = ctx.get("profile")
        if not profile:
            raise ValueError("No profile found in context")

        plugin_keywords = self._load_plugin_keywords()

        tiered = self._generate_candidates(profile, plugin_keywords)
        queries = self._select_queries(tiered)

        ctx["queries"] = queries
        ctx["ai_provider_used"] = "rules"
        return ctx

    def _load_plugin_keywords(self) -> dict[str, list[str]]:
        plugins = load_bundled_plugins(self._enabled_plugins)
        return get_plugin_keywords(plugins)

    # ── candidate generation (4 tiers) ─────────────────────────────────

    def _generate_candidates(
        self,
        profile: Any,
        plugin_keywords: dict[str, list[str]],
    ) -> dict[str, list[str]]:
        tiers: dict[str, list[str]] = {"a": [], "b": [], "c": [], "d": []}

        raw_text = getattr(profile, "raw_extracted_text", None) or ""

        skills: list[str] = list(profile.skills or [])
        roles: list[str] = [
            e.get("role", "") for e in (profile.experience or []) if e.get("role")
        ]
        locations: list[str] = list(profile.preferred_locations or [])
        companies: list[str] = list(profile.target_companies or [])
        profile_keywords: list[str] = list(profile.keywords or [])
        edu_fields: list[str] = [
            e.get("field", "") for e in (profile.education or []) if e.get("field")
        ]

        if raw_text.strip():
            extracted = _extract_skills_from_text(raw_text, _COMMON_SKILLS)
            for s in extracted:
                if s not in skills:
                    skills.append(s)
            remote_pref = getattr(profile, "remote_preference", None)
            if remote_pref and remote_pref not in locations:
                locations.append(remote_pref)

        industries = _infer_industries(skills, raw_text)

        # ── Tier A: skill/role/industry combined (no location) ────────

        for skill in skills:
            tiers["a"].append(f"{skill} jobs")
            for role in roles:
                tiers["a"].append(f"{skill} {role}")
            for field in edu_fields:
                tiers["a"].append(f"{skill} {field}")
        for role in roles:
            tiers["a"].append(f"{role} jobs")
        for field in edu_fields:
            tiers["a"].append(f"{field} jobs")
        for kw in profile_keywords:
            tiers["a"].append(kw)

        # Industry queries
        for ind in industries:
            tiers["a"].append(f"{ind} jobs")
            for role in roles:
                tiers["a"].append(f"{ind} {role}")
            for skill in skills[:3]:
                tiers["a"].append(f"{skill} {ind}")

        # Plugin keywords
        for _plugin_name, keywords in plugin_keywords.items():
            for kw in keywords:
                for skill in skills:
                    tiers["a"].append(f"{skill} {kw}")
                for role in roles:
                    tiers["a"].append(f"{role} {kw}")

        # ── Tier B: target_company-site queries ───────────────────────

        for company in companies:
            domain = _company_to_careers_domain(company)
            if domain:
                for role in roles or ["careers"]:
                    tiers["b"].append(f"site:{domain} {role}")
                for skill in skills[:2]:
                    tiers["b"].append(f"site:{domain} {skill} careers")
            else:
                for role in roles or [""]:
                    suffix = f" {role}" if role else ""
                    tiers["b"].append(f'"{company}" careers{suffix}')

        # ── Tier C: job-board-site queries ────────────────────────────

        for board in self._job_boards:
            for skill in skills[:3]:
                tiers["c"].append(f"site:{board} {skill} jobs")
            for role in roles[:2]:
                tiers["c"].append(f"site:{board} {role}")
            for ind in industries[:2]:
                tiers["c"].append(f"site:{board} {ind} jobs")

        # ── Tier D: location suffix on top candidates from A-C ────────

        if locations:
            seen_d: set[str] = set()
            for tier_key in ["a", "b", "c"]:
                for c in tiers[tier_key][:3]:
                    for loc in locations[:2]:
                        with_loc = f"{c} {loc}"
                        norm = with_loc.lower().strip()
                        if norm not in seen_d:
                            seen_d.add(norm)
                            tiers["d"].append(with_loc)

        return tiers

    # ── proportional query selection ───────────────────────────────────

    def _select_queries(self, tiered: dict[str, list[str]]) -> list[str]:
        seen: set[str] = set()

        def _dedup(items: list[str]) -> list[str]:
            out: list[str] = []
            for c in items:
                normal = c.lower().strip()
                if normal and normal not in seen:
                    seen.add(normal)
                    out.append(c.strip())
            return out

        deduped: dict[str, list[str]] = {}
        for k in TIER_KEYS:
            deduped[k] = _dedup(tiered.get(k, []))

        all_flat: list[str] = []
        for k in TIER_KEYS:
            all_flat.extend(deduped[k])

        if not all_flat:
            return list(FALLBACK_QUERIES)

        n = self._query_count
        if len(all_flat) <= n:
            return all_flat

        # Allocate slots proportionally
        slots: dict[str, int] = {}
        total_slots = 0
        for k in TIER_KEYS:
            s = max(0, int(n * TIER_PROPORTIONS[k]))
            slots[k] = s
            total_slots += s

        # Distribute remainder (favouring B and C)
        remainder = n - total_slots
        for k in ["c", "b", "a", "d"]:
            if remainder <= 0:
                break
            if deduped[k]:
                slots[k] += 1
                remainder -= 1

        result: list[str] = []
        for k in TIER_KEYS:
            result.extend(deduped[k][: slots[k]])

        # Fill any remaining slots from the flat pool
        if len(result) < n:
            remaining = [c for c in all_flat if c not in result]
            result.extend(remaining[: n - len(result)])

        return result[:n]


