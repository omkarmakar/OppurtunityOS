"""Secure API key storage — reads from environment variables or .secrets.json.

Keys are NEVER written to source code, .env files committed to git, or logs.
Environment variables take precedence over .secrets.json.

Usage:
    from core.secrets import get_secret, set_secret

    # Store a key (prompts once, saves to .secrets.json)
    set_secret("rapidapi_key", "your-key-here")

    # Retrieve a key (checks env var first, then .secrets.json)
    key = get_secret("rapidapi_key")
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

_SECRETS_FILE = Path(__file__).resolve().parent.parent / ".secrets.json"

# Environment variable name mapping (uppercase, prefixed)
_ENV_PREFIX = "OOS_SECRETS_"


def _load_secrets_file() -> dict[str, str]:
    """Load secrets from .secrets.json if it exists."""
    if not _SECRETS_FILE.exists():
        return {}
    try:
        with open(_SECRETS_FILE, encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return {}
        return {k: str(v) for k, v in data.items()}
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Failed to load %s: %s", _SECRETS_FILE, exc)
        return {}


def _save_secrets_file(secrets: dict[str, str]) -> None:
    """Save secrets to .secrets.json."""
    try:
        with open(_SECRETS_FILE, "w", encoding="utf-8") as f:
            json.dump(secrets, f, indent=2)
        # Restrict file permissions on Unix
        try:
            os.chmod(_SECRETS_FILE, 0o600)
        except OSError:
            pass
    except OSError as exc:
        logger.error("Failed to save %s: %s", _SECRETS_FILE, exc)


def get_secret(name: str) -> str | None:
    """Retrieve a secret by name.

    Priority order:
    1. Environment variable: OOS_SECRETS_<NAME_UPPER>
    2. .secrets.json file

    Returns None if not found.
    """
    # 1. Environment variable
    env_key = f"{_ENV_PREFIX}{name.upper()}"
    env_val = os.environ.get(env_key)
    if env_val:
        return env_val

    # 2. .secrets.json
    secrets = _load_secrets_file()
    return secrets.get(name)


def set_secret(name: str, value: str) -> None:
    """Store a secret persistently in .secrets.json.

    Also sets the environment variable for the current process.
    """
    secrets = _load_secrets_file()
    secrets[name] = value
    _save_secrets_file(secrets)

    # Set env var for current process
    env_key = f"{_ENV_PREFIX}{name.upper()}"
    os.environ[env_key] = value


def delete_secret(name: str) -> bool:
    """Remove a secret from .secrets.json. Returns True if deleted."""
    secrets = _load_secrets_file()
    if name in secrets:
        del secrets[name]
        _save_secrets_file(secrets)
        env_key = f"{_ENV_PREFIX}{name.upper()}"
        os.environ.pop(env_key, None)
        return True
    return False


def list_secrets() -> list[str]:
    """List all stored secret names (values not returned for safety)."""
    secrets = _load_secrets_file()
    env_keys = [
        k[len(_ENV_PREFIX):].lower()
        for k in os.environ
        if k.startswith(_ENV_PREFIX)
    ]
    return sorted(set(list(secrets.keys()) + env_keys))
