"""Settings response schema."""

from __future__ import annotations

from pydantic import BaseModel, Field


class DatabaseSettingsResponse(BaseModel):
    url: str = Field(description="Database connection URL (password redacted)")
    driver: str = Field(description="Database driver")
    echo: bool = Field(description="Echo SQL statements")
    pool_size: int = Field(description="Connection pool size")
    max_overflow: int = Field(description="Max overflow connections")


class LoggingSettingsResponse(BaseModel):
    level: str = Field(description="Minimum log level")
    rotation: str = Field(description="Log rotation interval")
    retention: str = Field(description="Log retention duration")
    directory: str = Field(description="Log output directory")


class ServerSettingsResponse(BaseModel):
    host: str = Field(description="Bind address")
    port: int = Field(description="Bind port")
    allowed_origins: list[str] = Field(description="CORS allowed origins")


class PluginSettingsResponse(BaseModel):
    enabled_plugins: list[str] = Field(description="Enabled plugin modules")
    plugin_dir: str = Field(description="Plugin discovery directory")


class PathSettingsResponse(BaseModel):
    data_dir: str = Field(description="Data storage directory")
    config_dir: str = Field(description="Configuration directory")
    log_dir: str = Field(description="Log output directory")
    asset_dir: str = Field(description="Asset files directory")


class SettingsResponse(BaseModel):
    app_name: str = Field(description="Application name")
    version: str = Field(description="Application version")
    environment: str = Field(description="Active environment")
    debug: bool = Field(description="Debug mode enabled")
    database: DatabaseSettingsResponse = Field(description="Database settings")
    logging: LoggingSettingsResponse = Field(description="Logging settings")
    server: ServerSettingsResponse = Field(description="Server settings")
    plugins: PluginSettingsResponse = Field(description="Plugin settings")
    paths: PathSettingsResponse = Field(description="Path settings")
