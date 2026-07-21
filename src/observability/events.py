"""Structured logging — one JSON-ish line per request/LLM call.

Observability is a day-one deliverable, never trailing. Log the input summary,
output summary, latency, and error — never the raw secret or full payload.
"""
from __future__ import annotations

import logging
import sys
import time
from contextlib import contextmanager
from collections.abc import Iterator

import structlog


def configure_logging(level: str = "INFO") -> None:
    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=level.upper())
    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, level.upper(), logging.INFO)
        ),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str = "agent") -> structlog.BoundLogger:
    return structlog.get_logger(name)


@contextmanager
def log_span(logger: structlog.BoundLogger, event: str, **fields) -> Iterator[dict]:
    """Time a unit of work; emits ``event`` with latency_ms and any error."""
    start = time.perf_counter()
    extra: dict = {}
    try:
        yield extra
    except Exception as exc:  # noqa: BLE001 — we re-raise after logging
        logger.error(event, latency_ms=round((time.perf_counter() - start) * 1000, 1),
                     error=type(exc).__name__, **fields, **extra)
        raise
    else:
        logger.info(event, latency_ms=round((time.perf_counter() - start) * 1000, 1),
                    **fields, **extra)
