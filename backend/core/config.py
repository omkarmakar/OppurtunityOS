"""Backend configuration — delegates to the central AppConfig.

Usage::

    from backend.core.config import get_backend_config

    cfg = get_backend_config()
    cfg.server.host   # "127.0.0.1"
    cfg.server.port   # 8000
"""

from __future__ import annotations

from core.config import AppConfig, ConfigurationProvider, get_config


def get_backend_config() -> AppConfig:
    """Return the central application configuration.

    Convenience wrapper around ``core.config.get_config()``.
    """
    return get_config()


def get_backend_config_provider() -> ConfigurationProvider:
    """Return an injectable configuration provider."""
    return ConfigurationProvider()
