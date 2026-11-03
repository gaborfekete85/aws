import pytest

from localbini_shared.consumers import make_event_handler
from localbini_shared.events import new_event
from localbini_shared.testing import eventbridge_event


def test_dispatches_by_detail_type_with_domain_event() -> None:
    seen = []
    handle = make_event_handler({"Ping": [seen.append]}, "test")
    event = new_event("Ping", {"n": 1}, service="t")
    handle(eventbridge_event(event.to_detail(), "Ping"), None)
    assert seen == [event]


def test_handler_errors_propagate_so_lambda_retries() -> None:
    def boom(_):
        raise RuntimeError("downstream failed")

    handle = make_event_handler({"Ping": [boom]}, "test")
    event = new_event("Ping", {}, service="t")
    with pytest.raises(RuntimeError, match="downstream failed"):
        handle(eventbridge_event(event.to_detail(), "Ping"), None)
