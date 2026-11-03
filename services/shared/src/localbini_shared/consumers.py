"""EventBridge consumers built on lbz's EventBroker.

lbz logs and swallows handler errors; for bus consumers that would silently drop
events, so this broker re-raises. Lambda's async-invoke retries and the
on-failure destination (DLQ) then take over.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import Any, cast

from lbz.events.broker import EventBroker
from lbz.events.event import Event as LbzEvent

from localbini_shared.events import DomainEvent
from localbini_shared.logging import bind_request, configure_logging, get_logger

logger = get_logger(__name__)

DomainHandler = Callable[[DomainEvent], None]


class RaisingEventBroker(EventBroker):
    def on_error(self, error: Exception) -> None:
        logger.exception("event handler failed", extra={"event_type": self.event.type})
        raise error


def _adapt(handler: DomainHandler) -> Callable[[LbzEvent], None]:
    def adapted(event: LbzEvent) -> None:
        domain_event = DomainEvent.from_detail(event.data)
        bind_request(domain_event.event_id, domain_event.correlation_id)
        handler(domain_event)

    adapted.__name__ = getattr(handler, "__name__", "handler")
    return adapted


def make_event_handler(
    mapper: Mapping[str, Sequence[DomainHandler]], service: str
) -> Callable[[dict[str, Any], Any], None]:
    """Lambda entrypoint dispatching EventBridge events by detail-type."""
    configure_logging(service)
    lbz_mapper = cast(
        Any, {type_: [_adapt(h) for h in handlers] for type_, handlers in mapper.items()}
    )

    def handle(event: dict[str, Any], context: Any) -> None:
        RaisingEventBroker(lbz_mapper, event, context).react()

    return handle
