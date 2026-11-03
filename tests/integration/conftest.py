"""Integration tests against a deployed environment.

Run after `terraform apply` (CI does this in the deploy workflow):

    export API_BASE_URL=$(terraform -chdir=infra/envs/dev output -raw api_endpoint)
    export BUS_SPY_QUEUE_URL=$(terraform -chdir=infra/envs/dev output -raw bus_spy_queue_url)
    export TEST_CLIENT_ID=$(terraform -chdir=infra/envs/dev output -raw test_client_id)
    export E2E_ORGANIZER_EMAIL=... E2E_ORGANIZER_PASSWORD=...
    export E2E_USER_EMAIL=... E2E_USER_PASSWORD=...
    uv run pytest tests/integration -m dev

Test data is isolated per run (unique titles with RUN_ID) and cleaned up: every
Event a test creates is cancelled at the end (Drafts are published first so they
can be cancelled; the domain allows no other way out).
"""

from __future__ import annotations

import json
import os
import time
import uuid
from collections.abc import Callable, Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

import boto3
import httpx
import pytest

RUN_ID = os.environ.get("GITHUB_RUN_ID") or uuid.uuid4().hex[:8]
REGION = os.environ.get("AWS_REGION", "eu-central-1")


def _require(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        pytest.skip(f"{name} not set; integration tests need a deployed environment")
    return value


@pytest.fixture(scope="session")
def base_url() -> str:
    return _require("API_BASE_URL").rstrip("/")


@pytest.fixture(scope="session")
def http(base_url: str) -> Iterator[httpx.Client]:
    with httpx.Client(base_url=base_url, timeout=30) as client:
        yield client


# --- identities --------------------------------------------------------------------
def _id_token(email: str, password: str) -> str:
    client = boto3.client("cognito-idp", region_name=REGION)
    result = client.initiate_auth(
        ClientId=_require("TEST_CLIENT_ID"),
        AuthFlow="USER_PASSWORD_AUTH",
        AuthParameters={"USERNAME": email, "PASSWORD": password},
    )
    token: str = result["AuthenticationResult"]["IdToken"]
    return token


@pytest.fixture(scope="session")
def organizer_headers() -> dict[str, str]:
    token = _id_token(_require("E2E_ORGANIZER_EMAIL"), _require("E2E_ORGANIZER_PASSWORD"))
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="session")
def attendee_headers() -> dict[str, str]:
    token = _id_token(_require("E2E_USER_EMAIL"), _require("E2E_USER_PASSWORD"))
    return {"Authorization": f"Bearer {token}"}


# --- the bus -----------------------------------------------------------------------
class BusSpy:
    """Reads the dev-only spy queue that receives every domain event on the bus."""

    def __init__(self, queue_url: str) -> None:
        self.queue_url = queue_url
        self.sqs = boto3.client("sqs", region_name=REGION)
        self.seen: list[dict[str, Any]] = []

    def _drain(self) -> None:
        response = self.sqs.receive_message(
            QueueUrl=self.queue_url, MaxNumberOfMessages=10, WaitTimeSeconds=2
        )
        for message in response.get("Messages", []):
            envelope = json.loads(message["Body"])
            self.seen.append({"type": envelope["detail-type"], **envelope["detail"]})
            self.sqs.delete_message(QueueUrl=self.queue_url, ReceiptHandle=message["ReceiptHandle"])

    def wait_for(
        self, type_: str, match: Callable[[dict[str, Any]], bool], timeout: float = 45
    ) -> dict[str, Any]:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            for event in self.seen:
                if event["type"] == type_ and match(event["data"]):
                    return event
            self._drain()
        seen = sorted({e["type"] for e in self.seen})
        raise AssertionError(f"{type_} not seen on the bus within {timeout}s (saw: {seen})")


@pytest.fixture(scope="session")
def bus() -> BusSpy:
    return BusSpy(_require("BUS_SPY_QUEUE_URL"))


# --- isolated test data -----------------------------------------------------------
def eventually(fn: Callable[[], Any], timeout: float = 30, interval: float = 1.5) -> Any:
    """Retry an assertion until it passes (projections are eventually consistent)."""
    deadline = time.monotonic() + timeout
    while True:
        try:
            return fn()
        except AssertionError:
            if time.monotonic() > deadline:
                raise
            time.sleep(interval)


@pytest.fixture
def make_event(
    http: httpx.Client, organizer_headers: dict[str, str]
) -> Iterator[Callable[..., dict]]:
    created: list[str] = []

    def _make(*, price_cents: int = 0, places: int = 5, publish: bool = True) -> dict:
        starts = (datetime.now(UTC) + timedelta(days=10)).replace(microsecond=0)
        body = {
            "title": f"IT {RUN_ID} {uuid.uuid4().hex[:6]}",
            "description": "Created by tests/integration; cancelled at teardown.",
            "important_information": "Integration test data.",
            "starts_at": starts.isoformat(),
            "ends_at": (starts + timedelta(hours=2)).isoformat(),
            "places": places,
            "price_cents": price_cents,
            "currency": "CHF",
            # exact coordinates: no dependency on the external geocoder
            "location": {
                "name": "Test hall",
                "address": "Teststrasse 1",
                "city": "Zürich",
                "lat": 47.37,
                "lng": 8.54,
            },
        }
        response = http.post("/events", json=body, headers=organizer_headers)
        assert response.status_code == 201, response.text
        event = response.json()
        created.append(event["id"])
        if publish:
            published = http.post(f"/events/{event['id']}/publish", headers=organizer_headers)
            assert published.status_code == 200, published.text
            event = published.json()
        return event

    yield _make

    for event_id in created:  # cleanup: nothing from this run stays bookable
        http.post(f"/events/{event_id}/publish", headers=organizer_headers)  # Drafts first
        http.post(f"/events/{event_id}/cancel", headers=organizer_headers)
