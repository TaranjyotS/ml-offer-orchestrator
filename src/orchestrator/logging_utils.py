# src/orchestrator/logging_utils.py
from __future__ import annotations

import logging
from typing import Callable

from src.orchestrator.middleware import request_id_ctx


def configure_logging() -> None:
    """
    Make request_id ALWAYS available on every LogRecord.
    This avoids formatter errors when logs are emitted outside request context.
    """
    old_factory: Callable[..., logging.LogRecord] = logging.getLogRecordFactory()

    def record_factory(*args, **kwargs) -> logging.LogRecord:
        record = old_factory(*args, **kwargs)
        # Ensure formatter never crashes
        if not hasattr(record, "request_id"):
            record.request_id = request_id_ctx.get()
        return record

    # Idempotent: don't re-wrap repeatedly
    current_factory = logging.getLogRecordFactory()
    if current_factory is record_factory:
        return

    logging.setLogRecordFactory(record_factory)

    # Optional: reduce noisy dependency logs (keeps your output clean)
    logging.getLogger("httpx").setLevel(logging.WARNING)
