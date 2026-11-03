"""Structured JSON logging for Lambda (CloudWatch Logs Insights friendly)."""

from __future__ import annotations

import json
import logging
import os
import sys
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any

_request_id: ContextVar[str | None] = ContextVar("request_id", default=None)
_correlation_id: ContextVar[str | None] = ContextVar("correlation_id", default=None)

_RESERVED = set(vars(logging.makeLogRecord({})).keys()) | {"message", "asctime"}


def bind_request(request_id: str | None, correlation_id: str | None = None) -> None:
    """Attach ids to every log line emitted while handling the current invocation."""
    _request_id.set(request_id)
    _correlation_id.set(correlation_id or request_id)


def current_correlation_id() -> str | None:
    return _correlation_id.get()


class JsonFormatter(logging.Formatter):
    def __init__(self, service: str) -> None:
        super().__init__()
        self.service = service

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "service": self.service,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if rid := _request_id.get():
            payload["request_id"] = rid
        if cid := _correlation_id.get():
            payload["correlation_id"] = cid
        for key, value in record.__dict__.items():
            if key not in _RESERVED and not key.startswith("_"):
                payload[key] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging(service: str | None = None, level: str | None = None) -> None:
    """Route all logging through one JSON handler on stdout. Idempotent."""
    service = service or os.environ.get("SERVICE_NAME", "meeton")
    level = level or os.environ.get("LOG_LEVEL", "INFO")
    root = logging.getLogger()
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter(service))
    root.handlers = [handler]
    root.setLevel(level)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
