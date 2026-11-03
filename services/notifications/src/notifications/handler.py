"""Notifications Lambda: consumes bus events from SQS with partial-batch failures.

Each SQS record holds one EventBridge event. A record whose handler raises is
reported in ``batchItemFailures``; only that record returns to the queue, and
after ``maxReceiveCount`` attempts SQS moves it to the DLQ.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from typing import Any

from meeton_shared.events import DomainEvent
from meeton_shared.logging import bind_request, configure_logging, get_logger

logger = get_logger(__name__)

Handler = Callable[[DomainEvent], None]


def process_batch(event: dict[str, Any], handlers: Mapping[str, Handler]) -> dict[str, Any]:
    failures: list[dict[str, str]] = []
    for record in event.get("Records", []):
        message_id = record["messageId"]
        try:
            envelope = json.loads(record["body"])
            domain_event = DomainEvent.from_eventbridge(envelope)
            bind_request(domain_event.event_id, domain_event.correlation_id)
            handler = handlers.get(domain_event.type)
            if handler is None:
                logger.warning("no handler; dropping", extra={"event_type": domain_event.type})
                continue
            handler(domain_event)
        except Exception:
            logger.exception("notification failed", extra={"message_id": message_id})
            failures.append({"itemIdentifier": message_id})
    return {"batchItemFailures": failures}


def make_sqs_handler(
    handlers: Mapping[str, Handler], service: str = "notifications"
) -> Callable[[dict[str, Any], Any], dict[str, Any]]:
    configure_logging(service)

    def handle(event: dict[str, Any], context: Any) -> dict[str, Any]:
        return process_batch(event, handlers)

    return handle
