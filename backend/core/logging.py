"""Backend logging configuration — uses central Loguru setup."""

from __future__ import annotations

from pathlib import Path

from core.config import get_config
from core.logging.logger import setup_logging


def configure_backend_logging(log_dir: Path | None = None) -> None:
    """Configure loguru for the backend application.

    Args:
        log_dir: Override for the log directory. Falls back to
                 ``get_config().logging.directory``.
    """
    cfg = get_config()

    resolved = log_dir or Path(cfg.paths.log_dir)
    setup_logging(
        log_dir=resolved,
        level=cfg.logging.level,
        rotation=cfg.logging.rotation,
        retention=cfg.logging.retention,
    )
