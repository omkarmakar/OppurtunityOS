"""Pydantic settings models with validation for all application domains."""

from __future__ import annotations

import warnings
from typing import ClassVar

from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseSettings(BaseModel):
    """SQLAlchemy database connection settings."""

    url: str = Field(
        default="sqlite:///./data/opportunity.db",
        description="Database connection URL",
    )
    echo: bool = Field(default=False, description="Echo SQL statements to stderr")
    pool_size: int = Field(default=5, ge=1, description="Connection pool size")
    max_overflow: int = Field(default=10, ge=0, description="Max overflow connections")

    @field_validator("url")
    @classmethod
    def _validate_url(cls, v: str) -> str:
        if not any(v.startswith(p) for p in ("sqlite", "postgresql", "mysql", "oracle")):
            msg = f"Unsupported database URL scheme: {v}"
            raise ValueError(msg)
        return v


class LoggingSettings(BaseModel):
    """Loguru logging configuration."""

    level: str = Field(default="DEBUG", description="Minimum log level")
    rotation: str = Field(default="1 day", description="Log file rotation interval")
    retention: str = Field(default="30 days", description="Log retention duration")
    directory: str = Field(default="logs", description="Log output directory")

    VALID_LEVELS: ClassVar[frozenset[str]] = frozenset(
        {"TRACE", "DEBUG", "INFO", "SUCCESS", "WARNING", "ERROR", "CRITICAL"}
    )

    @field_validator("level")
    @classmethod
    def _validate_level(cls, v: str) -> str:
        upper = v.upper()
        if upper not in cls.VALID_LEVELS:
            valid_str = ", ".join(sorted(cls.VALID_LEVELS))
            msg = f"Invalid log level: {v}. Must be one of: {valid_str}"
            raise ValueError(msg)
        return upper


class ServerSettings(BaseModel):
    """HTTP server settings for FastAPI."""

    host: str = Field(default="127.0.0.1", description="Bind address")
    port: int = Field(default=8000, ge=1, le=65535, description="Bind port")
    allowed_origins: list[str] = Field(
        default=["*"],
        description="CORS allowed origins",
    )

    @field_validator("port")
    @classmethod
    def _validate_port(cls, v: int) -> int:
        if not 1 <= v <= 65535:
            msg = f"Port must be between 1 and 65535, got {v}"
            raise ValueError(msg)
        return v


class BraveSearchSettings(BaseModel):
    """Brave Search API configuration."""

    api_key: str = Field(default="", description="Brave Search API key")
    base_url: str = Field(
        default="https://api.search.brave.com/res/v1/web/search",
        description="Brave Search API endpoint",
    )


class TavilySettings(BaseModel):
    """Tavily Search API configuration."""

    api_key: str = Field(default="", description="Tavily API key (starts with tvly-)")
    base_url: str = Field(
        default="https://api.tavily.com/search",
        description="Tavily Search API endpoint",
    )


class PluginSettings(BaseModel):
    """Plugin system configuration."""

    enabled_plugins: list[str] = Field(
        default_factory=list,
        description="List of enabled plugin module paths",
    )
    plugin_dir: str = Field(default="plugins", description="Plugin discovery directory")


class AISettings(BaseModel):
    """AI provider configuration."""

    openai_api_key: str = Field(default="", description="OpenAI API key")
    gemini_api_key: str = Field(default="", description="Google Gemini API key")
    openrouter_api_key: str = Field(default="", description="OpenRouter API key")
    groq_api_key: str = Field(default="", description="Groq API key")
    ollama_base_url: str = Field(
        default="http://localhost:11434",
        description="Ollama server base URL",
    )
    default_provider: str = Field(default="openrouter", description="Default AI provider name")
    default_model: str = Field(default="meta-llama/llama-3.3-70b-instruct:free", description="Default model name - verified free model on OpenRouter")
    fallback_providers: list[str] = Field(
        default_factory=lambda: ["groq", "gemini"],
        description="Ordered fallback providers tried after default_provider fails. "
                    "Set via OOS_AI__FALLBACK_PROVIDERS as a comma-separated string "
                    "(e.g. groq,gemini) or a JSON array (e.g. [\"groq\",\"gemini\"]).",
    )
    cache_ttl: int = Field(default=300, ge=0, description="Cache TTL in seconds")
    max_retries: int = Field(default=3, ge=0, le=10, description="Max retry attempts")


class EmailSettings(BaseModel):
    """SMTP email configuration."""

    smtp_host: str = Field(default="localhost", description="SMTP server host")
    smtp_port: int = Field(default=587, ge=1, le=65535, description="SMTP server port")
    smtp_username: str = Field(default="", description="SMTP username")
    smtp_password: str = Field(default="", description="SMTP password")
    smtp_use_tls: bool = Field(default=True, description="Use STARTTLS")
    from_address: str = Field(default="noreply@opportunityos.local", description="From email address")
    from_name: str = Field(default="OpportunityOS", description="From display name")


class DigestSettings(BaseModel):
    """Daily digest configuration."""

    schedule_hour: int = Field(default=8, ge=0, le=23, description="Hour for daily digest")
    schedule_minute: int = Field(default=0, ge=0, le=59, description="Minute for daily digest")
    max_opportunities: int = Field(default=20, ge=1, description="Max items in digest")
    include_unread_only: bool = Field(default=True, description="Only include unread notifications")


class NotificationSettings(BaseModel):
    """Notification delivery and scheduling configuration."""

    desktop_enabled: bool = Field(default=True, description="Enable desktop notifications")
    email_enabled: bool = Field(default=False, description="Enable email notifications")
    digest_enabled: bool = Field(default=False, description="Enable daily digest")
    polling_interval_seconds: int = Field(default=60, ge=10, le=3600, description="Scheduler polling interval")
    email: EmailSettings = Field(default_factory=EmailSettings)
    digest: DigestSettings = Field(default_factory=DigestSettings)


class BackgroundSchedulerSettings(BaseModel):
    """Background scheduler configuration."""

    enabled: bool = Field(default=True, description="Enable background scheduler")
    polling_interval_seconds: int = Field(default=30, ge=5, le=3600, description="Scheduler loop polling interval")
    default_user_id: str = Field(
        default="00000000-0000-0000-0000-000000000000",
        description="Default user for scheduled tasks",
    )

    # Pipeline task
    pipeline_enabled: bool = Field(default=False, description="Enable automatic pipeline runs")
    pipeline_interval_seconds: int = Field(
        default=3600, ge=60, le=604800,
        description="Legacy interval kept for backward compatibility; unused when window mode is active",
    )
    pipeline_search_provider: str = Field(default="tavily", description="Search provider for scheduled pipeline")
    pipeline_max_queries: int = Field(default=5, ge=1, le=20)
    pipeline_max_results: int = Field(default=10, ge=1, le=50)
    pipeline_retry_count: int = Field(default=3, ge=0, le=10)
    pipeline_retry_delay_base: int = Field(default=30, ge=1, le=600)

    # Pipeline window — calendar-day, local-time scheduling
    timezone: str = Field(
        default="Asia/Kolkata",
        description="IANA timezone name used for the daily pipeline window (e.g. 'Asia/Kolkata', 'America/New_York')",
    )
    pipeline_window_start_hour: int = Field(
        default=6, ge=0, le=23,
        description="Local hour (inclusive) at which the pipeline run window opens",
    )
    pipeline_window_end_hour: int = Field(
        default=12, ge=0, le=23,
        description="Local hour (exclusive) at which the pipeline run window closes",
    )

    # Digest task
    digest_enabled: bool = Field(default=False, description="Enable automatic digest via scheduler")
    digest_interval_seconds: int = Field(default=86400, ge=3600, le=604800, description="Digest run interval (seconds)")
    digest_retry_count: int = Field(default=2, ge=0, le=10)
    digest_retry_delay_base: int = Field(default=60, ge=1, le=600)


class MemorySettings(BaseModel):
    """ChromaDB vector memory configuration."""

    enabled: bool = Field(default=True, description="Enable vector memory")
    persist_directory: str = Field(
        default="data/memory",
        description="ChromaDB persistent storage directory (empty = in-memory)",
    )
    collection_name: str = Field(
        default="opportunityos_memory",
        description="ChromaDB collection name",
    )
    top_k: int = Field(default=10, ge=1, le=100, description="Default top-K for similarity search")


class PathSettings(BaseModel):
    """Filesystem path configuration."""

    data_dir: str = Field(default="data", description="Data storage directory")
    config_dir: str = Field(default="config", description="Configuration directory")
    log_dir: str = Field(default="logs", description="Log output directory")
    asset_dir: str = Field(default="assets", description="Asset files directory")


class AppConfig(BaseSettings):
    """Top-level application configuration.

    Loads values from the following sources (in precedence order):
      1. Pydantic field defaults (hardcoded)
      2. YAML configuration files (via ConfigManager)
      3. Environment variables / .env file

    Environment variable prefix: ``OOS_``
    Nested delimiter: ``__`` (e.g. ``OOS_DATABASE__URL``)
    """

    # ── top-level fields ──────────────────────────────────────────────
    app_name: str = Field(default="OpportunityOS", description="Application name")
    version: str = Field(default="0.1.0", description="Application version")
    environment: str = Field(
        default="development",
        description="Active environment (development|testing|production)",
    )
    debug: bool = Field(default=True, description="Enable debug mode")
    secret_key: str = Field(
        default="change-me-in-production",
        description="Application secret key",
    )

    # ── nested settings domains ───────────────────────────────────────
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)
    server: ServerSettings = Field(default_factory=ServerSettings)
    brave_search: BraveSearchSettings = Field(default_factory=BraveSearchSettings)
    tavily: TavilySettings = Field(default_factory=TavilySettings)
    ai: AISettings = Field(default_factory=AISettings)
    plugins: PluginSettings = Field(default_factory=PluginSettings)
    paths: PathSettings = Field(default_factory=PathSettings)
    notifications: NotificationSettings = Field(default_factory=NotificationSettings)
    background_scheduler: BackgroundSchedulerSettings = Field(default_factory=BackgroundSchedulerSettings)
    memory: MemorySettings = Field(default_factory=MemorySettings)

    model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(
        env_file=".env",
        env_prefix="OOS_",
        env_nested_delimiter="__",
        extra="ignore",
        frozen=False,
    )

    # ── validators ────────────────────────────────────────────────────

    @field_validator("environment")
    @classmethod
    def _validate_environment(cls, v: str) -> str:
        valid = {"development", "testing", "production"}
        lower = v.lower()
        if lower not in valid:
            valid_str = ", ".join(sorted(valid))
            msg = f"Environment must be one of {{{valid_str}}}, got {v!r}"
            raise ValueError(msg)
        return lower

    @field_validator("secret_key")
    @classmethod
    def _warn_default_secret(cls, v: str) -> str:
        if v == "change-me-in-production":
            warnings.warn(
                "Secret key is still set to the insecure default. "
                "Override via OOS_SECRET_KEY in production.",
                stacklevel=2,
            )
        return v
