import os
import subprocess
import sys


def test_health_handler_works_with_only_event_bus_name_set() -> None:
    """Lambda sets EVENT_BUS_NAME only; lbz must not demand its own EVENTS_BUS_NAME."""
    env = {
        k: v
        for k, v in os.environ.items()
        if k not in {"EVENTS_BUS_NAME", "AWS_LAMBDA_FUNCTION_NAME"}
    }
    env["EVENT_BUS_NAME"] = "localbini-dev"
    code = (
        "from localbini_shared.health import handle;"
        "from localbini_shared.testing import http_api_event;"
        "print(handle(http_api_event('GET', '/health'), None)['statusCode'])"
    )
    out = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True)
    assert out.stdout.strip().endswith("200"), out.stderr
