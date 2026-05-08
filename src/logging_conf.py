"""JSON line logging via structlog."""

from __future__ import annotations

from typing import Any

import structlog

structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso", utc=True, key="ts"),
        structlog.processors.JSONRenderer(),
    ],
    logger_factory=structlog.PrintLoggerFactory(),
)

_log = structlog.get_logger("modelmix")


def log_event(event: str, **fields: Any) -> None:
    _log.info(event, **fields)
