"""Integration tests against a deployed environment.

Run after `terraform apply`:

    API_BASE_URL=$(terraform -chdir=infra/envs/dev output -raw api_endpoint) \
      uv run pytest tests/integration -m dev
"""

from __future__ import annotations

import os
from collections.abc import Iterator

import httpx
import pytest


@pytest.fixture(scope="session")
def base_url() -> str:
    url = os.environ.get("API_BASE_URL")
    if not url:
        pytest.skip("API_BASE_URL not set; integration tests need a deployed environment")
    return url.rstrip("/")


@pytest.fixture(scope="session")
def http(base_url: str) -> Iterator[httpx.Client]:
    with httpx.Client(base_url=base_url, timeout=15) as client:
        yield client
