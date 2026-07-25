"""Frontend user context helpers."""

from __future__ import annotations

from core.config import get_config


def get_active_user_id() -> str:
    return get_config().background_scheduler.default_user_id
