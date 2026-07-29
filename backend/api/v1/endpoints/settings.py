"""Settings endpoint."""

from __future__ import annotations

from urllib.parse import urlparse, urlunparse

from fastapi import APIRouter, Depends

from backend.api.deps import get_app_config
from backend.schemas.settings import (
    DatabaseSettingsResponse,
    IntegrationStatus,
    LoggingSettingsResponse,
    PathSettingsResponse,
    PluginSettingsResponse,
    ServerSettingsResponse,
    SettingsResponse,
)
from core.config import AppConfig
from core.secrets import get_secret

router = APIRouter()


def _redact_db_url(url: str) -> str:
    if not url:
        return ""
    parsed = urlparse(url)
    if parsed.password:
        netloc = f"{parsed.username}:****@{parsed.hostname}"
        if parsed.port:
            netloc += f":{parsed.port}"
        parsed = parsed._replace(netloc=netloc)
    result = urlunparse(parsed)
    # urlunparse normalizes sqlite:/// to sqlite:/, so restore the triple slash
    if url.startswith("sqlite:///") and result.startswith("sqlite:/") and not result.startswith("sqlite:///"):
        result = result.replace("sqlite:/", "sqlite:///", 1)
    return result


@router.get("/settings", response_model=SettingsResponse)
def get_settings(cfg: AppConfig = Depends(get_app_config)) -> SettingsResponse:
    return SettingsResponse(
        app_name=cfg.app_name,
        version=cfg.version,
        environment=cfg.environment,
        debug=cfg.debug,
        database=DatabaseSettingsResponse(
            url=_redact_db_url(cfg.database.url),
            driver=cfg.database.url.split("://")[0] if "://" in cfg.database.url else "unknown",
            echo=cfg.database.echo,
            pool_size=cfg.database.pool_size,
            max_overflow=cfg.database.max_overflow,
        ),
        logging=LoggingSettingsResponse(
            level=cfg.logging.level,
            rotation=cfg.logging.rotation,
            retention=cfg.logging.retention,
            directory=cfg.logging.directory,
        ),
        server=ServerSettingsResponse(
            host=cfg.server.host,
            port=cfg.server.port,
            allowed_origins=cfg.server.allowed_origins,
        ),
        plugins=PluginSettingsResponse(
            enabled_plugins=cfg.plugins.enabled_plugins,
            plugin_dir=cfg.plugins.plugin_dir,
        ),
        paths=PathSettingsResponse(
            data_dir=cfg.paths.data_dir,
            config_dir=cfg.paths.config_dir,
            log_dir=cfg.paths.log_dir,
            asset_dir=cfg.paths.asset_dir,
        ),
        configuration_status=_build_configuration_status(cfg),
    )


_INTEGRATIONS: list[tuple[str, str, str]] = [
    ("brave_search", "OOS_BRAVE_SEARCH__API_KEY", "Get a key at https://brave.com/search/api/"),
    ("openai", "OOS_AI__OPENAI_API_KEY", "Get a key at https://platform.openai.com/api-keys"),
    ("gemini", "OOS_AI__GEMINI_API_KEY", "Get a key at https://aistudio.google.com/apikey"),
    ("openrouter", "OOS_AI__OPENROUTER_API_KEY", "Get a key at https://openrouter.ai/settings/keys"),
    ("groq", "OOS_AI__GROQ_API_KEY", "Get a key at https://console.groq.com/keys"),
    ("ollama", "", "No API key needed — set OOS_AI__OLLAMA_BASE_URL if not at localhost:11434"),
]

# Job board RapidAPI providers — each has its own secret, fallback to shared rapidapi_key
_JOBBOARD_INTEGRATIONS: list[tuple[str, str, str, str]] = [
    # (name, secret_name, host, description)
    ("JSearch (Google for Jobs)", "rapidapi_key_jsearch", "jsearch.p.rapidapi.com", "Aggregates from Indeed, LinkedIn, ZipRecruiter"),
    ("Active Jobs DB (Fantastic.jobs)", "rapidapi_key_active_jobs_db", "active-jobs-db.p.rapidapi.com", "ATS job listings with skills, experience"),
    ("LinkedIn Job Search (Fantastic.jobs)", "rapidapi_key_linkedin_jobs", "linkedin-job-search-api.p.rapidapi.com", "LinkedIn job board listings"),
    ("Glassdoor Real-Time", "rapidapi_key_glassdoor", "real-time-glassdoor-data.p.rapidapi.com", "Glassdoor jobs + company interviews"),
    ("Indeed (Mantiks)", "rapidapi_key_indeed", "indeed12.p.rapidapi.com", "Indeed search + company-targeted"),
    ("Remote Jobs1", "rapidapi_key_remote_jobs", "remote-jobs1.p.rapidapi.com", "Remote ATS jobs (Workable, Ashby, etc.)"),
]


def _build_configuration_status(cfg: AppConfig) -> list[IntegrationStatus]:
    result: list[IntegrationStatus] = []
    for name, env_var, hint in _INTEGRATIONS:
        configured = _is_configured(name, cfg)
        result.append(IntegrationStatus(name=name, configured=configured, env_var=env_var, hint=hint))

    # Add job board integrations
    for name, secret_name, host, hint in _JOBBOARD_INTEGRATIONS:
        # Check per-provider key first, then shared key
        key = get_secret(secret_name) or get_secret("rapidapi_key")
        configured = bool(key)
        env_var = f"OOS_SECRETS_{secret_name.upper()}"
        result.append(IntegrationStatus(
            name=f"Job Board: {name}",
            configured=configured,
            env_var=env_var,
            hint=f"{hint} ({host})",
        ))

    return result


def _is_configured(name: str, cfg: AppConfig) -> bool:
    if name == "brave_search":
        return bool(cfg.brave_search.api_key)
    if name == "openai":
        return bool(cfg.ai.openai_api_key)
    if name == "gemini":
        return bool(cfg.ai.gemini_api_key)
    if name == "openrouter":
        return bool(cfg.ai.openrouter_api_key)
    if name == "groq":
        return bool(cfg.ai.groq_api_key)
    if name == "ollama":
        return True
    return False


# ── Job board test connection & quota status ────────────────────────

from pydantic import BaseModel


class JobBoardTestRequest(BaseModel):
    provider_name: str


class JobBoardTestResponse(BaseModel):
    provider_name: str
    success: bool
    message: str
    results_count: int = 0


class JobBoardQuotaResponse(BaseModel):
    provider_name: str
    remaining: int | None = None
    limit: int | None = None
    reset_at: float | None = None
    last_updated: str | None = None


@router.post("/settings/jobboards/test", response_model=JobBoardTestResponse)
async def test_jobboard_connection(req: JobBoardTestRequest):
    """Test a job board provider with a single cheap search call."""
    from services.job_boards.aggregator import JobBoardAggregator
    agg = JobBoardAggregator()
    board = agg.get_board(req.provider_name)
    if not board:
        return JobBoardTestResponse(
            provider_name=req.provider_name,
            success=False,
            message=f"Unknown provider: {req.provider_name}",
        )
    try:
        import asyncio
        results = await board.search(["software engineer"], max_results=1)
        return JobBoardTestResponse(
            provider_name=req.provider_name,
            success=True,
            message=f"Connected — returned {len(results)} result(s)",
            results_count=len(results),
        )
    except Exception as exc:
        return JobBoardTestResponse(
            provider_name=req.provider_name,
            success=False,
            message=f"Error: {exc}",
        )


@router.get("/settings/jobboards/quota", response_model=list[JobBoardQuotaResponse])
def get_jobboard_quota():
    """Get quota status for all job board providers."""
    from database.session import SessionLocal
    from database.repositories.quota_state_repository import QuotaStateRepository

    db = SessionLocal()
    try:
        repo = QuotaStateRepository(db)
        states = repo.get_all_providers()
        return [
            JobBoardQuotaResponse(
                provider_name=s.provider_name,
                remaining=s.remaining,
                limit=s.quota_limit,
                reset_at=s.reset_at,
                last_updated=s.last_updated_at.isoformat() if s.last_updated_at else None,
            )
            for s in states
        ]
    finally:
        db.close()
