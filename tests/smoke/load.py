"""Async smoke / load test (asyncio + aiohttp).

1. optionally creates and publishes a free Event with --places places (Organizer token);
2. fires --searches concurrent Event searches;
3. fires --bookings concurrent Booking attempts (1 place each) at that one Event;
4. asserts **no overbooking** (confirmed <= places, places_left == places - confirmed)
   and reports latency percentiles per operation.

Exit code 1 on overbooking, on an error rate above --max-error-rate, or when
p95 latency exceeds --p95-budget-ms.

    uv run python tests/smoke/load.py --base-url $API --searches 200 --bookings 50 \
        --places 20 --concurrency 25 --organizer-token $ORG --attendee-token $USER
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import statistics
import sys
import time
import uuid
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

import aiohttp


@dataclass
class Stats:
    latencies_ms: dict[str, list[float]] = field(default_factory=lambda: defaultdict(list))
    statuses: dict[str, Counter[int]] = field(default_factory=lambda: defaultdict(Counter))
    errors: dict[str, int] = field(default_factory=lambda: defaultdict(int))

    def record(self, op: str, status: int, elapsed_ms: float) -> None:
        self.latencies_ms[op].append(elapsed_ms)
        self.statuses[op][status] += 1

    @staticmethod
    def percentile(values: list[float], pct: float) -> float:
        if not values:
            return 0.0
        ordered = sorted(values)
        rank = math.ceil(pct / 100 * len(ordered))  # nearest-rank definition
        return ordered[min(len(ordered), max(1, rank)) - 1]

    def report(self) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for op, values in self.latencies_ms.items():
            out[op] = {
                "requests": len(values),
                "statuses": dict(self.statuses[op]),
                "errors": self.errors[op],
                "p50_ms": round(self.percentile(values, 50), 1),
                "p90_ms": round(self.percentile(values, 90), 1),
                "p95_ms": round(self.percentile(values, 95), 1),
                "p99_ms": round(self.percentile(values, 99), 1),
                "max_ms": round(max(values), 1),
                "mean_ms": round(statistics.fmean(values), 1),
            }
        return out


class Client:
    def __init__(self, session: aiohttp.ClientSession, base_url: str, stats: Stats) -> None:
        self.session = session
        self.base_url = base_url.rstrip("/")
        self.stats = stats

    async def call(
        self, op: str, method: str, path: str, *, token: str | None = None, **kwargs: Any
    ) -> tuple[int, Any]:
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        start = time.perf_counter()
        try:
            async with self.session.request(
                method, f"{self.base_url}{path}", headers=headers, **kwargs
            ) as response:
                body = await response.json(content_type=None)
                status = response.status
        except (TimeoutError, aiohttp.ClientError):
            self.stats.errors[op] += 1
            self.stats.record(op, 0, (time.perf_counter() - start) * 1000)
            return 0, None
        self.stats.record(op, status, (time.perf_counter() - start) * 1000)
        if status >= 500:
            self.stats.errors[op] += 1
        return status, body


async def create_event(client: Client, token: str, places: int, lat: float, lng: float) -> str:
    starts = (datetime.now(UTC) + timedelta(days=5)).replace(microsecond=0)
    body = {
        "title": f"Load test {uuid.uuid4().hex[:6]}",
        "starts_at": starts.isoformat(),
        "ends_at": (starts + timedelta(hours=1)).isoformat(),
        "places": places,
        "price_cents": 0,
        "currency": "CHF",
        "location": {
            "name": "Load",
            "address": "Loadstrasse 1",
            "city": "Zürich",
            "lat": lat,
            "lng": lng,
        },
    }
    status, event = await client.call("setup", "POST", "/events", token=token, json=body)
    if status != 201:
        raise SystemExit(f"could not create the load-test Event: {status} {event}")
    status, _ = await client.call("setup", "POST", f"/events/{event['id']}/publish", token=token)
    if status != 200:
        raise SystemExit(f"could not publish: {status}")
    return str(event["id"])


async def wait_until_bookable(
    client: Client, event_id: str, timeout_s: float = 60
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        status, body = await client.call("availability", "GET", f"/events/{event_id}/availability")
        if status == 200 and body.get("open"):
            return dict(body)
        await asyncio.sleep(1)
    raise SystemExit("the Event never became bookable (Booking projection lagging?)")


async def bounded(n: int, concurrency: int, make: Any) -> list[Any]:
    semaphore = asyncio.Semaphore(concurrency)

    async def one(i: int) -> Any:
        async with semaphore:
            return await make(i)

    return await asyncio.gather(*(one(i) for i in range(n)))


async def run(args: argparse.Namespace) -> int:
    stats = Stats()
    timeout = aiohttp.ClientTimeout(total=args.timeout_s)
    connector = aiohttp.TCPConnector(limit=args.concurrency)
    async with aiohttp.ClientSession(timeout=timeout, connector=connector) as session:
        client = Client(session, args.base_url, stats)

        event_id = args.event_id
        if not event_id:
            if not args.organizer_token:
                raise SystemExit("give --event-id or --organizer-token to create one")
            event_id = await create_event(
                client, args.organizer_token, args.places, args.lat, args.lng
            )
        before = await wait_until_bookable(client, event_id)
        places_before = int(before["places_left"])

        params = {"lat": args.lat, "lng": args.lng, "radius_km": args.radius_km}
        started = time.perf_counter()
        await bounded(
            args.searches,
            args.concurrency,
            lambda _: client.call("search", "GET", "/events", params=params),
        )
        results = await bounded(
            args.bookings,
            args.concurrency,
            lambda _: client.call(
                "book",
                "POST",
                f"/events/{event_id}/bookings",
                token=args.attendee_token,
                json={"places": 1},
            ),
        )
        wall_s = time.perf_counter() - started

        _, after = await client.call("availability", "GET", f"/events/{event_id}/availability")
        if args.organizer_token and not args.event_id and not args.keep_event:
            await client.call(
                "setup", "POST", f"/events/{event_id}/cancel", token=args.organizer_token
            )

    confirmed = sum(1 for status, _ in results if status == 201)
    rejected = sum(1 for status, _ in results if status == 409)
    places_left = int(after["places_left"]) if after else -1
    overbooked = (
        confirmed > places_before or places_left != places_before - confirmed or places_left < 0
    )

    total = sum(len(v) for v in stats.latencies_ms.values())
    errors = sum(stats.errors.values())
    error_rate = errors / total if total else 0.0
    report = stats.report()
    p95_breaches = [
        op
        for op in ("search", "book")
        if op in report and report[op]["p95_ms"] > args.p95_budget_ms
    ]
    summary = {
        "event_id": event_id,
        "wall_s": round(wall_s, 2),
        "throughput_rps": round((args.searches + args.bookings) / wall_s, 1) if wall_s else None,
        "places_before": places_before,
        "bookings_confirmed": confirmed,
        "bookings_rejected_409": rejected,
        "places_left_after": places_left,
        "overbooked": overbooked,
        "error_rate": round(error_rate, 4),
        "p95_budget_breaches": p95_breaches,
        "operations": report,
    }
    print(json.dumps(summary, indent=2))

    if overbooked:
        print("FAIL: overbooking detected", file=sys.stderr)
        return 1
    if error_rate > args.max_error_rate:
        print(f"FAIL: error rate {error_rate:.2%} > {args.max_error_rate:.2%}", file=sys.stderr)
        return 1
    if p95_breaches:
        print(f"FAIL: p95 over {args.p95_budget_ms} ms for {p95_breaches}", file=sys.stderr)
        return 1
    print("OK: no overbooking, error rate and latency within budget", file=sys.stderr)
    return 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("--base-url", required=True)
    p.add_argument("--event-id", help="existing free Published Event (otherwise one is created)")
    p.add_argument("--organizer-token", help="ID token of an Organizer (to create the Event)")
    p.add_argument("--attendee-token", required=True, help="ID token used for the Booking attempts")
    p.add_argument("--searches", type=int, default=100)
    p.add_argument("--bookings", type=int, default=30)
    p.add_argument("--places", type=int, default=10)
    p.add_argument("--concurrency", type=int, default=20)
    p.add_argument("--lat", type=float, default=47.3769)
    p.add_argument("--lng", type=float, default=8.5417)
    p.add_argument("--radius-km", type=float, default=10)
    p.add_argument("--timeout-s", type=float, default=30)
    p.add_argument("--max-error-rate", type=float, default=0.01)
    p.add_argument("--p95-budget-ms", type=float, default=1500)
    p.add_argument("--keep-event", action="store_true")
    return p.parse_args(argv)


if __name__ == "__main__":
    sys.exit(asyncio.run(run(parse_args())))
