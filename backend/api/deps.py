"""FastAPI dependency injection module."""

from __future__ import annotations

from typing import Generator

from core.config import AppConfig, ConfigurationProvider, get_config
from database.session import SessionLocal


def get_db() -> Generator:
    """Provide a database session for dependency injection."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_config_provider() -> ConfigurationProvider:
    """Provide a configuration provider for dependency injection."""
    return ConfigurationProvider()


def get_app_config() -> AppConfig:
    """Provide the application configuration for dependency injection."""
    return get_config()
