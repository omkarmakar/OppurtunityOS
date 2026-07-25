"""Configuration system — auto-loaded, validated, injectable.

Usage::

    from core.config import get_config, ConfigurationProvider

    cfg = get_config()
    cfg.database.url          # "sqlite:///./data/opportunity.db"
    cfg.server.port           # 8000
    cfg.environment           # "development"

    # Dependency injection
    provider = ConfigurationProvider()
    provider.config.logging.level  # "DEBUG"

    # Testing override
    from core.config import reload_config
    reload_config(environment="testing")
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from core.config.config_manager import ConfigManager

# Load .env early so all env vars are available to both ConfigManager and
# Pydantic's BaseSettings.
load_dotenv()

from core.config.settings import (  # noqa: E402  (import after dotenv)
    AppConfig,
    BackgroundSchedulerSettings,
    DatabaseSettings,
    DigestSettings,
    EmailSettings,
    LoggingSettings,
    MemorySettings,
    NotificationSettings,
    PathSettings,
    PluginSettings,
    ServerSettings,
)

__all__ = [
    "AppConfig",
    "BackgroundSchedulerSettings",
    "ConfigurationProvider",
    "DatabaseSettings",
    "DigestSettings",
    "EmailSettings",
    "LoggingSettings",
    "MemorySettings",
    "NotificationSettings",
    "PathSettings",
    "PluginSettings",
    "ServerSettings",
    "get_config",
    "reload_config",
]

# ── module-level singleton ──────────────────────────────────────────────

_config_instance: AppConfig | None = None

_PROJECT_ROOTS: tuple[str, ...] = (
    # Typical locations for the config/ directory
    str(Path(__file__).resolve().parent.parent.parent),  # package-root
    os.getcwd(),  # current working directory
)


def _find_config_dir() -> Path:
    """Locate the ``config/`` directory.

    Resolution order:
        1. ``OOS_CONFIG_DIR`` environment variable (absolute path)
        2. Known project roots (package tree, current working directory)
        3. Fall back to ``{cwd}/config`` (will be created on first use)
    """
    env_override = os.environ.get("OOS_CONFIG_DIR")
    if env_override:
        candidate = Path(env_override)
        if candidate.is_dir():
            return candidate.resolve()

    for root in _PROJECT_ROOTS:
        candidate = Path(root) / "config"
        if candidate.is_dir():
            return candidate.resolve()
    # Fall back to cwd + config (may not exist yet)
    return Path(os.getcwd()) / "config"


def get_config() -> AppConfig:
    """Return the application-wide configuration singleton.

    The config is lazily loaded on first call and cached thereafter.
    Configuration sources (lowest to highest precedence):

        1. Pydantic field defaults
        2. ``config/default.yaml``
        3. ``config/{environment}.yaml`` (deep-merged)
        4. ``.env`` file / system environment variables (``OOS_*``)

    Returns:
        The validated ``AppConfig`` instance.
    """
    global _config_instance

    if _config_instance is not None:
        return _config_instance

    env = os.environ.get("OOS_ENVIRONMENT", "development")

    config_dir = _find_config_dir()
    manager = ConfigManager(config_dir)
    merged: dict[str, Any] = manager.load_for_environment(env)

    # Ensure the environment field matches what was actually requested
    merged.setdefault("environment", env)

    _config_instance = AppConfig(**merged)
    return _config_instance


def reload_config(
    environment: str | None = None,
    config_dir: Path | None = None,
) -> AppConfig:
    """Force-reload the configuration singleton (useful in tests).

    Args:
        environment: Override the active environment.
        config_dir:  Override the configuration directory.

    Returns:
        The newly created ``AppConfig`` instance.
    """
    global _config_instance

    _config_instance = None

    if environment is not None:
        os.environ["OOS_ENVIRONMENT"] = environment
    if config_dir is not None:
        os.environ["OOS_CONFIG_DIR"] = str(config_dir.resolve())

    return get_config()


# ── dependency-injection provider ───────────────────────────────────────


class ConfigurationProvider:
    """Injectable configuration provider for clean-architecture modules.

    Accepts an optional pre-built config for testing with mocks.
    Defaults to the module-level singleton when called without arguments.

    Usage::

        # Inside a service constructor
        self._config = ConfigurationProvider().config
    """

    def __init__(self, config: AppConfig | None = None) -> None:
        """Initialize the provider.

        Args:
            config: A pre-built config instance (for testing/mocking).
        """
        self._config: AppConfig = config or get_config()

    @property
    def config(self) -> AppConfig:
        """Return the held configuration instance."""
        return self._config
