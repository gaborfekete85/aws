"""Measure every packaged Lambda in the official arm64 runtime image (input for docs/cost.md).

For each handler: start ``public.ecr.aws/lambda/python:3.13-arm64`` with the zip,
time a cold invoke (includes module import = Lambda init) and the median of warm
invokes, then read the container's memory with ``docker stats``. The Runtime
Interface Emulator reports Max Memory Used = configured size, so container RSS
(which slightly overestimates: it includes the emulator) is used instead.

    docker compose up -d && scripts/build_all_lambdas.sh
    uv run python scripts/measure_lambdas.py
"""

from __future__ import annotations

import json
import statistics
import subprocess
import tempfile
import time
import urllib.request
import zipfile
from pathlib import Path

from meeton_shared.testing import http_api_event as http

ROOT = Path(__file__).resolve().parents[1]
DB = "postgresql+psycopg://meeton:meeton@host.docker.internal:5432/catalog"
DDB = "http://host.docker.internal:8000"

CASES = [
    ("health", "shared.zip", "meeton_shared.health.handle", http("GET", "/health"), {}),
    (
        "catalog-api (search)",
        "catalog.zip",
        "catalog.api.handle",
        http("GET", "/events", query={"lat": "47.37", "lng": "8.54", "radius_km": "10"}),
        {"DATABASE_URL": DB},
    ),
    (
        "booking-api (availability)",
        "booking.zip",
        "booking.api.handle",
        http("GET", "/events/{event_id}/availability", path_params={"event_id": "x"}),
        {"DYNAMODB_ENDPOINT_URL": DDB, "BOOKINGS_TABLE": "meeton-local-bookings"},
    ),
    (
        "booking-expiry (sweep)",
        "booking.zip",
        "booking.expiry.handle",
        {},
        {"DYNAMODB_ENDPOINT_URL": DDB, "BOOKINGS_TABLE": "meeton-local-bookings"},
    ),
    (
        "payments-api (checkout)",
        "payments.zip",
        "payments.api.handle",
        http("GET", "/bookings/{booking_id}/checkout", path_params={"booking_id": "x"}),
        {"DYNAMODB_ENDPOINT_URL": DDB, "PAYMENTS_TABLE": "missing"},
    ),
    (
        "notifications (empty batch)",
        "notifications.zip",
        "notifications.app.handle",
        {"Records": []},
        {"NOTIFICATIONS_TABLE": "x", "SENDER_EMAIL": "x@example.com"},
    ),
    (
        "identity-api (403 path)",
        "identity.zip",
        "identity.api.handle",
        http("GET", "/admin/users"),
        {"USER_POOL_ID": "x"},
    ),
]


def invoke(port: int, payload: dict) -> float:
    url = f"http://localhost:{port}/2015-03-31/functions/function/invocations"
    request = urllib.request.Request(url, data=json.dumps(payload).encode(), method="POST")
    start = time.perf_counter()
    with urllib.request.urlopen(request, timeout=60) as response:  # noqa: S310 (localhost)
        response.read()
    return (time.perf_counter() - start) * 1000


def memory_mb(container: str) -> float:
    out = (
        subprocess.run(  # noqa: S603
            ["docker", "stats", "--no-stream", "--format", "{{.MemUsage}}", container],  # noqa: S607
            capture_output=True,
            text=True,
            check=True,
        )
        .stdout.split("/")[0]
        .strip()
    )
    value, unit = float(out[:-3]), out[-3:]
    return value * (1024 if unit == "GiB" else 1 / 1024 if unit == "KiB" else 1)


def main() -> None:
    rows = []
    with tempfile.TemporaryDirectory() as tmp:
        for i, (name, zip_name, handler, payload, env) in enumerate(CASES):
            target = Path(tmp) / str(i)
            zipfile.ZipFile(ROOT / "dist" / zip_name).extractall(target)
            port = 9200 + i
            args = [
                "docker",
                "run",
                "-d",
                "--rm",
                "-p",
                f"{port}:8080",
                "-v",
                f"{target}:/var/task:ro",
            ]
            base_env = {
                "EVENT_BUS_NAME": "local",
                "AWS_DEFAULT_REGION": "eu-central-1",
                "AWS_ACCESS_KEY_ID": "local",
                "AWS_SECRET_ACCESS_KEY": "local",
            }
            for key, value in {**base_env, **env}.items():
                args += ["-e", f"{key}={value}"]
            container = subprocess.run(  # noqa: S603
                [*args, "public.ecr.aws/lambda/python:3.13-arm64", handler],
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()
            try:
                time.sleep(1.5)
                cold = invoke(port, payload)
                warm = statistics.median(invoke(port, payload) for _ in range(5))
                rows.append((name, zip_name, cold, warm, memory_mb(container)))
            finally:
                subprocess.run(["docker", "stop", container], capture_output=True)  # noqa: S603,S607

    print("| Handler | Package | Cold invoke (ms) | Warm median (ms) | Memory (MB) |")
    print("|---|---|---|---|---|")
    for name, zip_name, cold, warm, mem in rows:
        size = (ROOT / "dist" / zip_name).stat().st_size / 1024 / 1024
        print(f"| {name} | {zip_name} ({size:.0f} MB) | {cold:.0f} | {warm:.1f} | {mem:.0f} |")


if __name__ == "__main__":
    main()
