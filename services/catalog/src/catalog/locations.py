"""Application service: build a Location from what the Organizer typed."""

from __future__ import annotations

from dataclasses import dataclass

from catalog.domain import GeoPoint, Location
from catalog.geocoding import Geocoder, geocode_sync


@dataclass(frozen=True)
class LocationInput:
    name: str
    address: str
    city: str
    lat: float | None = None
    lng: float | None = None


def resolve_location(data: LocationInput, geocoder: Geocoder) -> Location:
    """Geocode the address, unless the client already sent exact coordinates (map pin)."""
    if data.lat is not None and data.lng is not None:
        point = GeoPoint(data.lat, data.lng)
    else:
        point = geocode_sync(geocoder, data.address, data.city).point
    return Location(name=data.name, address=data.address, city=data.city, point=point)


def location_changed(current: Location, data: LocationInput) -> bool:
    return (current.name, current.address, current.city) != (
        data.name,
        data.address,
        data.city,
    ) or (
        data.lat is not None
        and data.lng is not None
        and (data.lat, data.lng) != (current.point.lat, current.point.lng)
    )
