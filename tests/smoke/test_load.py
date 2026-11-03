"""The load script's verdicts, against mocked HTTP (aioresponses)."""

import re
import sys
from pathlib import Path

import pytest
from aioresponses import aioresponses

sys.path.insert(0, str(Path(__file__).parent))

import load

BASE = "http://api.test"


def args(**overrides):
    values = [
        "--base-url",
        BASE,
        "--event-id",
        "e1",
        "--attendee-token",
        "t",
        "--searches",
        "5",
        "--bookings",
        "6",
        "--concurrency",
        "3",
    ]
    parsed = load.parse_args(values)
    for key, value in overrides.items():
        setattr(parsed, key, value)
    return parsed


def mock_backend(mocked, *, places: int, confirm: int, left_after: int) -> None:
    availability = re.compile(rf"^{BASE}/events/e1/availability$")
    mocked.get(availability, payload={"open": True, "places_left": places})
    mocked.get(re.compile(rf"^{BASE}/events\?.*$"), payload={"items": []}, repeat=True)
    for i in range(6):
        status = 201 if i < confirm else 409
        mocked.post(f"{BASE}/events/e1/bookings", status=status, payload={})
    mocked.get(availability, payload={"open": True, "places_left": left_after})


async def test_passes_when_bookings_respect_places() -> None:
    with aioresponses() as mocked:
        mock_backend(mocked, places=4, confirm=4, left_after=0)
        assert await load.run(args()) == 0


async def test_fails_on_overbooking() -> None:
    with aioresponses() as mocked:
        mock_backend(mocked, places=4, confirm=6, left_after=-2)  # a broken backend
        assert await load.run(args()) == 1


async def test_fails_when_counter_and_confirmations_disagree() -> None:
    with aioresponses() as mocked:
        mock_backend(mocked, places=4, confirm=3, left_after=0)  # one place lost
        assert await load.run(args()) == 1


async def test_fails_on_p95_budget() -> None:
    with aioresponses() as mocked:
        mock_backend(mocked, places=4, confirm=4, left_after=0)
        assert await load.run(args(p95_budget_ms=0.0)) == 1


@pytest.mark.parametrize(("pct", "expected"), [(50, 5), (90, 9), (95, 10), (99, 10)])
def test_percentiles(pct, expected) -> None:
    assert load.Stats.percentile([float(v) for v in range(1, 11)], pct) == expected
