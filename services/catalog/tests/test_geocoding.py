"""Geocoder tests with mocked HTTP (aioresponses)."""

import re

import pytest
from aioresponses import aioresponses
from catalog.domain import GeoPoint
from catalog.geocoding import (
    USER_AGENT,
    AddressNotFound,
    GeocoderUnavailable,
    NominatimGeocoder,
)
from catalog.locations import LocationInput, location_changed, resolve_location
from localbini_shared.errors import ValidationError

URL = "https://geo.test/search"
MATCH = re.compile(r"^https://geo\.test/search\?.*$")
FOUND = [{"lat": "47.3601", "lon": "8.5354", "display_name": "Mythenquai 9, Zürich"}]


def geocoder(**kwargs) -> NominatimGeocoder:
    return NominatimGeocoder(URL, backoff_s=0, **kwargs)


async def test_resolves_address_to_point() -> None:
    with aioresponses() as mocked:
        mocked.get(MATCH, payload=FOUND)
        result = await geocoder().geocode("Mythenquai 9", "Zürich")
    assert result.point == GeoPoint(47.3601, 8.5354)
    assert result.display_name == "Mythenquai 9, Zürich"


async def test_sends_query_and_identifying_user_agent() -> None:
    with aioresponses() as mocked:
        mocked.get(MATCH, payload=FOUND)
        await geocoder().geocode("Mythenquai 9", "Zürich")
        ((key, calls),) = mocked.requests.items()
    assert key[1].query["q"] == "Mythenquai 9, Zürich"
    assert key[1].query["format"] == "jsonv2"
    assert calls[0].kwargs["headers"]["User-Agent"] == USER_AGENT


async def test_no_match_is_a_clear_validation_error() -> None:
    with aioresponses() as mocked:
        mocked.get(MATCH, payload=[])
        with pytest.raises(AddressNotFound) as info:
            await geocoder().geocode("Nowhere 1", "Atlantis")
    assert isinstance(info.value, ValidationError)
    assert info.value.details == {"field": "address"}
    assert "Atlantis" in info.value.message


async def test_retries_on_5xx_then_succeeds() -> None:
    with aioresponses() as mocked:
        mocked.get(MATCH, status=503)
        mocked.get(MATCH, status=429)
        mocked.get(MATCH, payload=FOUND)
        result = await geocoder(attempts=3).geocode("Mythenquai 9", "Zürich")
    assert result.point.lat == pytest.approx(47.3601)


async def test_retries_on_timeout_then_gives_up() -> None:
    with aioresponses() as mocked:
        for _ in range(3):
            mocked.get(MATCH, exception=TimeoutError())
        with pytest.raises(GeocoderUnavailable) as info:
            await geocoder(attempts=3).geocode("Mythenquai 9", "Zürich")
    assert info.value.details["reason"] == "TimeoutError"


async def test_client_error_is_not_retried() -> None:
    with aioresponses() as mocked:
        mocked.get(MATCH, status=403)
        with pytest.raises(GeocoderUnavailable, match="right now"):
            await geocoder(attempts=3).geocode("Mythenquai 9", "Zürich")
        assert sum(len(c) for c in mocked.requests.values()) == 1


async def test_empty_address_never_calls_out() -> None:
    with aioresponses() as mocked, pytest.raises(AddressNotFound):
        await geocoder().geocode("  ", "")
    assert not mocked.requests


async def test_malformed_answer_is_reported() -> None:
    with aioresponses() as mocked:
        mocked.get(MATCH, payload=[{"lat": "not-a-number", "lon": "8"}])
        with pytest.raises(GeocoderUnavailable, match="unexpected"):
            await geocoder().geocode("x", "y")


class FakeGeocoder:
    def __init__(self) -> None:
        self.calls = 0

    async def geocode(self, address: str, city: str):
        from catalog.geocoding import GeocodeResult

        self.calls += 1
        return GeocodeResult(GeoPoint(46.0, 7.0), f"{address}, {city}")


def test_resolve_location_geocodes_from_sync_code() -> None:
    fake = FakeGeocoder()
    location = resolve_location(LocationInput("Hall", "Main St 1", "Bern"), fake)
    assert location.point == GeoPoint(46.0, 7.0)
    assert fake.calls == 1


def test_resolve_location_trusts_explicit_coordinates() -> None:
    fake = FakeGeocoder()
    location = resolve_location(LocationInput("Hall", "Main St 1", "Bern", 46.9, 7.4), fake)
    assert location.point == GeoPoint(46.9, 7.4)
    assert fake.calls == 0


def test_location_changed() -> None:
    fake = FakeGeocoder()
    loc = resolve_location(LocationInput("Hall", "Main St 1", "Bern"), fake)
    assert not location_changed(loc, LocationInput("Hall", "Main St 1", "Bern"))
    assert location_changed(loc, LocationInput("Hall", "Main St 2", "Bern"))
    assert location_changed(loc, LocationInput("Hall", "Main St 1", "Bern", 1.0, 2.0))
