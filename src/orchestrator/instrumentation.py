from __future__ import annotations

import time
import logging
from functools import wraps
from typing import Any, Awaitable, Callable, TypeVar, cast

T = TypeVar("T")


def timed(logger: logging.Logger, name: str) -> Callable[[Callable[..., Awaitable[T]]], Callable[..., Awaitable[T]]]:
    """Async timing decorator for structured latency logs."""

    def decorator(fn: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        @wraps(fn)
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            start = time.perf_counter()
            try:
                return await fn(*args, **kwargs)
            finally:
                ms = (time.perf_counter() - start) * 1000
                logger.info("%s latency_ms=%.2f", name, ms)

        return cast(Callable[..., Awaitable[T]], wrapper)

    return decorator
