"""Turn a Location address into coordinates with an external geocoder (asyncio + aiohttp).

Default provider: Nominatim (OpenStreetMap). Its usage policy requires an
identifying User-Agent and at most ~1 request/second, which fits Organizers
creating Events by hand.
"""

from __future__ import annotations

import asyncio
import os
import random
from dataclasses import dataclass
from typing import Any, Protocol

import aiohttp

from catalog.domain import GeoPoint
from meeton_shared.errors import ValidationError
from meeton_shared.logging import get_logger

logger = get_logger(__name__)

DEFAULT_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "Meeton/0.1 (+https://github.com/gaborfekete85/aws)"
RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})


class AddressNotFound(ValidationError):
    """The address does not resolve to a place; shown to the Organizer as a field error."""


class GeocoderUnavailable(ValidationError):
    """The geocoder kept failing; the Organizer can retry."""


@dataclass(frozen=True)
class GeocodeResult:
    point: GeoPoint
    display_name: str


class Geocoder(Protocol):
    async def geocode(self, address: str, city: str) -> GeocodeResult: ...


class NominatimGeocoder:
    def __init__(
        self,
        base_url: str | None = None,
        *,
        timeout_s: float = 4.0,
        attempts: int = 3,
        backoff_s: float = 0.4,
        session: aiohttp.ClientSession | None = None,
    ) -> None:
        self.base_url = base_url or os.environ.get("GEOCODER_URL", DEFAULT_URL)
        self.timeout = aiohttp.ClientTimeout(total=timeout_s)
        self.attempts = attempts
        self.backoff_s = backoff_s
        self._session = session

    async def geocode(self, address: str, city: str) -> GeocodeResult:
        query = ", ".join(part.strip() for part in (address, city) if part and part.strip())
        if not query:
            raise AddressNotFound("An address is required", details={"field": "address"})
        params = {"q": query, "format": "jsonv2", "limit": "1", "addressdetails": "0"}

        if self._session is not None:
            return await self._with_retries(self._session, params, query)
        async with aiohttp.ClientSession(
            timeout=self.timeout, headers={"User-Agent": USER_AGENT}
        ) as session:
            return await self._with_retries(session, params, query)

    async def _with_retries(
        self, session: aiohttp.ClientSession, params: dict[str, str], query: str
    ) -> GeocodeResult:
        last_error: str = "unknown error"
        for attempt in range(1, self.attempts + 1):
            try:
                async with session.get(
                    self.base_url,
                    params=params,
                    timeout=self.timeout,
                    headers={"User-Agent": USER_AGENT},
                ) as response:
                    if response.status in RETRYABLE_STATUS:
                        last_error = f"HTTP {response.status}"
                    elif response.status >= 400:
                        raise GeocoderUnavailable(
                            "The address could not be checked right now",
                            details={"field": "address", "reason": f"HTTP {response.status}"},
                        )
                    else:
                        payload: Any = await response.json(content_type=None)
                        return self._parse(payload, query)
            except (TimeoutError, aiohttp.ClientError) as error:
                last_error = type(error).__name__
            logger.warning(
                "geocoder attempt failed",
                extra={"attempt": attempt, "error": last_error},
            )
            if attempt < self.attempts:
                # exponential backoff with jitter: 0.4s, 0.8s, ...
                delay = self.backoff_s * 2 ** (attempt - 1)
                await asyncio.sleep(delay + random.uniform(0, delay / 2))  # noqa: S311
        raise GeocoderUnavailable(
            "The address could not be checked right now, please try again",
            details={"field": "address", "reason": last_error},
        )

    @staticmethod
    def _parse(payload: Any, query: str) -> GeocodeResult:
        if not isinstance(payload, list) or not payload:
            raise AddressNotFound(
                f"We could not find '{query}'. Check the address and city.",
                details={"field": "address"},
            )
        first = payload[0]
        try:
            point = GeoPoint(lat=float(first["lat"]), lng=float(first["lon"]))
        except (KeyError, TypeError, ValueError) as error:
            raise GeocoderUnavailable(
                "The geocoder returned an unexpected answer", details={"field": "address"}
            ) from error
        return GeocodeResult(point=point, display_name=str(first.get("display_name", query)))


def geocode_sync(geocoder: Geocoder, address: str, city: str) -> GeocodeResult:
    """Bridge for the synchronous lbz handler: run the coroutine on a fresh loop."""
    return asyncio.run(geocoder.geocode(address, city))
