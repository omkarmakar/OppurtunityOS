"""Centralized logging configuration using Loguru."""

from __future__ import annotations

import sys
from pathlib import Path

from loguru import logger


def setup_logging(
    log_dir: str | Path = "logs",
    level: str = "DEBUG",
    rotation: str = "1 day",
    retention: str = "30 days",
) -> None:
    """Configure the global logger instance.

    Args:
        log_dir: Directory for log file output.
        level: Minimum log level.
        rotation: Log rotation schedule.
        retention: Log retention duration.
    """
    logger.remove()

    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)

    logger.add(
        sys.stderr,
        level=level.upper(),
        format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    )

    logger.add(
        log_path / "opportunity_{time:YYYY-MM-DD}.log",
        rotation=rotation,
        retention=retention,
        level=level.upper(),
        compression="gz",
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message}",
    )
