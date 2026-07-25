"""Comprehensive tests for the configuration system.

Covers:
  - ConfigManager (YAML loading, deep-merge, legacy API)
  - Pydantic AppConfig (defaults, validation, env-var override)
  - get_config / reload_config singleton lifecycle
  - ConfigurationProvider DI wrapper
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, Generator

import pytest
import yaml
from pydantic import ValidationError

from core.config import (
    AppConfig,
    ConfigurationProvider,
    DatabaseSettings,
    LoggingSettings,
    PathSettings,
    PluginSettings,
    ServerSettings,
    get_config,
    reload_config,
)
from core.config.config_manager import ConfigManager

# ── helpers ─────────────────────────────────────────────────────────────


def _write_yaml(path: Path, data: dict[str, Any]) -> Path:
    """Write a dictionary to a YAML file and return its path."""
    path.write_text(yaml.dump(data, default_flow_style=False), encoding="utf-8")
    return path


@pytest.fixture(autouse=True)
def _reset_config() -> Generator[None, None, None]:
    """Reset the config singleton before and after every test.

    This prevents cross-test pollution from the module-level cache.
    """
    # Capture original env
    original_env = os.environ.get("OOS_ENVIRONMENT")
    original_config_dir = os.environ.get("OOS_CONFIG_DIR")

    yield

    # Restore env
    if original_env is not None:
        os.environ["OOS_ENVIRONMENT"] = original_env
    else:
        os.environ.pop("OOS_ENVIRONMENT", None)

    if original_config_dir is not None:
        os.environ["OOS_CONFIG_DIR"] = original_config_dir
    else:
        os.environ.pop("OOS_CONFIG_DIR", None)

    reload_config()


@pytest.fixture
def config_dir_with_default(tmp_path: Path) -> Path:
    """Create a temporary config directory with a minimal default.yaml."""
    cfg_dir = tmp_path / "config"
    cfg_dir.mkdir()
    _write_yaml(
        cfg_dir / "default.yaml",
        {
            "app_name": "TestApp",
            "database": {"url": "sqlite:///./test.db", "echo": True},
        },
    )
    return cfg_dir


# ═══════════════════════════════════════════════════════════════════════
#  ConfigManager
# ═══════════════════════════════════════════════════════════════════════


class TestConfigManager:
    """YAML file loading and deep-merging."""

    def test_load_nonexistent_file_returns_empty_dict(self, tmp_path: Path) -> None:
        manager = ConfigManager(tmp_path)
        data = manager.load("nonexistent.yaml")
        assert data == {}

    def test_load_valid_yaml(self, tmp_path: Path) -> None:
        cfg_dir = tmp_path / "config"
        cfg_dir.mkdir()
        _write_yaml(
            cfg_dir / "settings.yaml",
            {"key": "value", "nested": {"a": 1}},
        )
        manager = ConfigManager(cfg_dir)
        data = manager.load("settings.yaml")
        assert data == {"key": "value", "nested": {"a": 1}}

    def test_load_for_environment_merges_with_default(self, tmp_path: Path) -> None:
        cfg_dir = tmp_path / "config"
        cfg_dir.mkdir()
        _write_yaml(cfg_dir / "default.yaml", {"debug": False, "database": {"echo": False}})
        _write_yaml(cfg_dir / "testing.yaml", {"debug": True, "database": {"pool_size": 10}})

        manager = ConfigManager(cfg_dir)
        merged = manager.load_for_environment("testing")

        assert merged["debug"] is True  # overridden
        assert merged["database"]["echo"] is False  # inherited from default
        assert merged["database"]["pool_size"] == 10  # added by testing

    def test_deep_merge_replaces_scalar_with_dict(self, tmp_path: Path) -> None:
        cfg_dir = tmp_path / "config"
        cfg_dir.mkdir()
        _write_yaml(cfg_dir / "default.yaml", {"plugins": "legacy_value"})
        _write_yaml(cfg_dir / "testing.yaml", {"plugins": {"enabled": ["x"]}})

        manager = ConfigManager(cfg_dir)
        merged = manager.load_for_environment("testing")
        assert merged["plugins"] == {"enabled": ["x"]}

    def test_legacy_get_after_load(self, tmp_path: Path) -> None:
        cfg_dir = tmp_path / "config"
        cfg_dir.mkdir()
        _write_yaml(
            cfg_dir / "test.yaml",
            {"database": {"host": "localhost", "port": 5432}},
        )
        manager = ConfigManager(cfg_dir)
        manager.load("test.yaml")
        assert manager.get("database.host") == "localhost"

    def test_legacy_get_missing_key_returns_default(self, tmp_path: Path) -> None:
        manager = ConfigManager(tmp_path)
        assert manager.get("missing.key", "fallback") == "fallback"

    def test_load_for_nonexistent_environment_falls_back_to_default(
        self, tmp_path: Path
    ) -> None:
        cfg_dir = tmp_path / "config"
        cfg_dir.mkdir()
        _write_yaml(cfg_dir / "default.yaml", {"key": "from_default"})

        manager = ConfigManager(cfg_dir)
        merged = manager.load_for_environment("nonexistent_env")
        assert merged == {"key": "from_default"}


# ═══════════════════════════════════════════════════════════════════════
#  Pydantic domain models
# ═══════════════════════════════════════════════════════════════════════


class TestDatabaseSettings:
    """DatabaseSettings validation."""

    def test_defaults(self) -> None:
        s = DatabaseSettings()
        assert s.url == "sqlite:///./data/opportunity.db"
        assert s.echo is False
        assert s.pool_size == 5
        assert s.max_overflow == 10

    def test_invalid_url_raises(self) -> None:
        with pytest.raises(ValidationError):
            DatabaseSettings(url="not-a-valid-db-scheme://localhost/db")


class TestLoggingSettings:
    """LoggingSettings validation."""

    def test_defaults(self) -> None:
        s = LoggingSettings()
        assert s.level == "DEBUG"

    def test_level_is_uppercased(self) -> None:
        s = LoggingSettings(level="info")
        assert s.level == "INFO"

    def test_invalid_level_raises(self) -> None:
        with pytest.raises(ValidationError):
            LoggingSettings(level="bogus")


class TestServerSettings:
    """ServerSettings validation."""

    def test_defaults(self) -> None:
        s = ServerSettings()
        assert s.host == "127.0.0.1"
        assert s.port == 8000

    def test_port_too_low_raises(self) -> None:
        with pytest.raises(ValidationError):
            ServerSettings(port=0)

    def test_port_too_high_raises(self) -> None:
        with pytest.raises(ValidationError):
            ServerSettings(port=70000)


class TestPluginSettings:
    def test_defaults(self) -> None:
        s = PluginSettings()
        assert s.enabled_plugins == []
        assert s.plugin_dir == "plugins"


class TestPathSettings:
    def test_defaults(self) -> None:
        s = PathSettings()
        assert s.data_dir == "data"
        assert s.log_dir == "logs"


# ═══════════════════════════════════════════════════════════════════════
#  AppConfig (top-level model)
# ═══════════════════════════════════════════════════════════════════════


class TestAppConfig:
    """AppConfig validation and env-var override behaviour."""

    def test_defaults(self) -> None:
        cfg = AppConfig()
        assert cfg.app_name == "OpportunityOS"
        assert cfg.environment == "development"
        assert cfg.debug is True
        assert isinstance(cfg.database, DatabaseSettings)
        assert isinstance(cfg.logging, LoggingSettings)
        assert isinstance(cfg.server, ServerSettings)
        assert isinstance(cfg.plugins, PluginSettings)
        assert isinstance(cfg.paths, PathSettings)

    def test_from_dict(self) -> None:
        cfg = AppConfig(**{"app_name": "Custom", "database": {"url": "sqlite:///./custom.db"}})
        assert cfg.app_name == "Custom"
        assert cfg.database.url == "sqlite:///./custom.db"

    @pytest.mark.parametrize("env", ["development", "testing", "production"])
    def test_valid_environments(self, env: str) -> None:
        cfg = AppConfig(environment=env)
        assert cfg.environment == env

    def test_invalid_environment_raises(self) -> None:
        with pytest.raises(ValidationError):
            AppConfig(environment="staging")

    def test_environments_are_lowercased(self) -> None:
        cfg = AppConfig(environment="PRODUCTION")
        assert cfg.environment == "production"

    def test_secret_key_warning(self) -> None:
        import warnings

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            AppConfig()
            default_warnings = [x for x in w if "Secret key" in str(x.message)]
            assert len(default_warnings) == 1

    def test_environment_variable_override(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OOS_APP_NAME", "EnvApp")
        monkeypatch.setenv("OOS_DATABASE__POOL_SIZE", "42")
        cfg = AppConfig()
        assert cfg.app_name == "EnvApp"
        assert cfg.database.pool_size == 42

    def test_allowed_origins_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OOS_SERVER__ALLOWED_ORIGINS", '["http://localhost:3000"]')
        cfg = AppConfig()
        assert cfg.server.allowed_origins == ["http://localhost:3000"]


# ═══════════════════════════════════════════════════════════════════════
#  get_config / reload_config singleton
# ═══════════════════════════════════════════════════════════════════════


class TestGetConfig:
    """Global configuration singleton lifecycle."""

    def test_returns_app_config_instance(self) -> None:
        cfg = get_config()
        assert isinstance(cfg, AppConfig)

    def test_singleton_returns_same_object(self) -> None:
        a = get_config()
        b = get_config()
        assert a is b

    def test_reload_config_creates_new_instance(self) -> None:
        a = get_config()
        b = reload_config()
        assert b is not a

    def test_reload_config_with_testing_env(self, config_dir_with_default: Path) -> None:
        """reload_config(environment="testing") should load testing.yaml values."""
        cfg = reload_config(environment="testing", config_dir=config_dir_with_default)
        assert cfg.environment == "testing"

    def test_configuration_provider_wraps_config(self) -> None:
        cfg = get_config()
        provider = ConfigurationProvider()
        assert provider.config is cfg

    def test_configuration_provider_accepts_mock(self) -> None:
        mock = AppConfig(app_name="Mocked")
        provider = ConfigurationProvider(config=mock)
        assert provider.config.app_name == "Mocked"
        assert provider.config is not get_config()


# ═══════════════════════════════════════════════════════════════════════
#  Integration — backend / database modules consume correct config
# ═══════════════════════════════════════════════════════════════════════


class TestIntegration:
    """Verify that dependent modules use the config correctly."""

    def test_backend_config_delegates_to_core(self) -> None:
        from backend.core.config import get_backend_config

        cfg = get_backend_config()
        assert isinstance(cfg, AppConfig)

    def test_database_session_uses_config_url(self) -> None:
        from database.session import engine

        assert "opportunity" in engine.url.render_as_string(hide_password=False)

    def test_paths_from_config(self) -> None:
        cfg = get_config()
        assert cfg.paths.data_dir == "data"
        assert cfg.paths.log_dir == "logs"

    def test_yaml_defaults_are_loaded(self) -> None:
        cfg = get_config()
        # default.yaml has app_name: "OpportunityOS"
        assert cfg.app_name == "OpportunityOS"
        # server.host is set in default.yaml and not overridden in development.yaml
        assert cfg.server.host == "127.0.0.1"
        assert cfg.server.port == 8000
