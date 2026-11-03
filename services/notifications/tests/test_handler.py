"""SQS consumption with partial-batch failures."""

from meeton_shared.events import new_event
from notifications.handler import process_batch

from .conftest import sqs_record


def record_for(type_: str, data: dict, message_id: str):
    event = new_event(type_, data, service="booking")
    return sqs_record(type_, event.to_detail(), message_id)


def test_only_failed_records_are_reported() -> None:
    seen = []

    def handler(event):
        if event.data.get("fail"):
            raise RuntimeError("SES throttled")
        seen.append(event.data["n"])

    batch = {
        "Records": [
            record_for("Ping", {"n": 1}, "m1"),
            record_for("Ping", {"n": 2, "fail": True}, "m2"),
            record_for("Ping", {"n": 3}, "m3"),
        ]
    }
    result = process_batch(batch, {"Ping": handler})
    assert result == {"batchItemFailures": [{"itemIdentifier": "m2"}]}
    assert seen == [1, 3]


def test_unknown_types_are_dropped_not_retried() -> None:
    assert process_batch({"Records": [record_for("Other", {}, "m1")]}, {}) == {
        "batchItemFailures": []
    }


def test_malformed_body_is_a_failure() -> None:
    record = {"messageId": "bad", "body": "not json"}
    assert process_batch({"Records": [record]}, {}) == {
        "batchItemFailures": [{"itemIdentifier": "bad"}]
    }
