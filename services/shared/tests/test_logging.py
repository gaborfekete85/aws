import json
import logging

from meeton_shared.logging import JsonFormatter, bind_request


def test_json_formatter_includes_ids_and_extra_fields() -> None:
    bind_request("req-9", "corr-9")
    record = logging.makeLogRecord(
        {
            "name": "x",
            "levelname": "INFO",
            "msg": "hello %s",
            "args": ("world",),
            "booking_id": "b1",
        }
    )
    line = json.loads(JsonFormatter("booking").format(record))
    assert line["message"] == "hello world"
    assert line["service"] == "booking"
    assert line["request_id"] == "req-9"
    assert line["correlation_id"] == "corr-9"
    assert line["booking_id"] == "b1"
