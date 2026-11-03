"""Lambda entrypoint: event type → notification handler (filled in by #31 / #32)."""

from __future__ import annotations

from notifications.handler import Handler, make_sqs_handler

HANDLERS: dict[str, Handler] = {}

handle = make_sqs_handler(HANDLERS)
