"""Settings endpoint."""

from __future__ import annotations

from urllib.parse import urlparse, urlunparse

from fastapi import APIRouter, Depends

from backend.api.deps import get_app_config
from backend.schemas.settings import (
    DatabaseSettingsResponse,
    LoggingSettingsResponse,
    PathSettingsResponse,
    PluginSettingsResponse,
    ServerSettingsResponse,
    SettingsResponse,
)
from core.config import AppConfig

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
    )
