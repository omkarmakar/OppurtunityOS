"""Retry logic with exponential backoff for AI provider calls."""

from __future__ import annotations

import asyncio
import random
from collections.abc import Awaitable, Callable
from functools import wraps
from typing import ParamSpec, TypeVar

P = ParamSpec("P")
R = TypeVar("R")


async def retry_with_backoff(
    func: Callable[P, Awaitable[R]],
    *args: P.args,
    **kwargs: P.kwargs,
) -> R:
    """Execute an async call with exponential backoff retry."""
    max_retries: int = kwargs.pop("_max_retries", 3)
    base_delay: float = kwargs.pop("_base_delay", 1.0)
    max_delay: float = kwargs.pop("_max_delay", 30.0)
    retryable_exceptions: tuple = kwargs.pop(
        "_retryable_exceptions",
        (TimeoutError, ConnectionError),
    )

    last_exc: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            return await func(*args, **kwargs)
        except retryable_exceptions as e:
            last_exc = e
            if attempt < max_retries:
                delay = min(base_delay * (2**attempt) + random.uniform(0, 0.5), max_delay)
                await asyncio.sleep(delay)
        except Exception:
            raise

    msg = f"All {max_retries + 1} retry attempts failed"
    raise RuntimeError(msg) from last_exc


def retryable(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
) -> Callable[[Callable[P, Awaitable[R]]], Callable[P, Awaitable[R]]]:
    """Decorator: wrap an async function with retry logic."""

    def decorator(
        func: Callable[P, Awaitable[R]],
    ) -> Callable[P, Awaitable[R]]:
        @wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            return await retry_with_backoff(
                func,
                *args,
                **kwargs,
                _max_retries=max_retries,
                _base_delay=base_delay,
                _max_delay=max_delay,
            )

        return wrapper

    return decorator
