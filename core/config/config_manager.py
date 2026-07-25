"""Multi-environment YAML configuration loader with deep merging."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


class ConfigManager:
    """Loads, merges, and provides access to YAML configuration files.

    Usage::

        manager = ConfigManager(Path("config"))
        merged = manager.load_for_environment("production")
    """

    def __init__(self, config_dir: Path) -> None:
        """Initialize the config manager.

        Args:
            config_dir: Directory containing YAML configuration files.
        """
        self._config_dir = config_dir
        self._data: dict[str, Any] = {}

    # ── public API ────────────────────────────────────────────────────

    def load(self, filename: str) -> dict[str, Any]:
        """Load a single YAML file and return its contents as a dict.

        Args:
            filename: Name of the YAML file (e.g. ``default.yaml``).

        Returns:
            Parsed YAML content, or an empty dict if the file does not exist.
        """
        filepath = self._config_dir / filename
        if not filepath.exists():
            self._data = {}
            return {}
        with open(filepath, encoding="utf-8") as f:
            data: dict[str, Any] | None = yaml.safe_load(f)
        self._data = data or {}
        return self._data

    def load_for_environment(self, environment: str) -> dict[str, Any]:
        """Load the base config and overlay environment-specific overrides.

        Load order:
            1. ``default.yaml`` (base values)
            2. ``{environment}.yaml`` (deep-merge overrides)

        Args:
            environment: Active environment key (development, testing, production).

        Returns:
            Deep-merged configuration dictionary.
        """
        merged = self.load("default.yaml")
        env_config = self.load(f"{environment}.yaml")
        if env_config:
            merged = self._deep_merge(merged, env_config)
        self._data = merged
        return merged

    # ── helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
        """Recursively merge *override* into *base*.

        When both values for a key are dicts, the merge recurses;
        otherwise the override value wins.
        """
        result = base.copy()
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = ConfigManager._deep_merge(result[key], value)
            else:
                result[key] = value
        return result

    # ── compatibility shim ────────────────────────────────────────────

    def get(self, key: str, default: Any = None) -> Any:
        """Access a value by dot-separated key (legacy API).

        Args:
            key: Dot-separated path (e.g. ``database.host``).
            default: Fallback value.

        Returns:
            The value at *key* or *default*.
        """
        keys = key.split(".")
        value: Any = self._data
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                return default
        return value if value is not None else default
