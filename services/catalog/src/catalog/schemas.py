"""Request/response shapes for the Catalog HTTP API (pydantic)."""

from __future__ import annotations

from typing import Any

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from catalog.domain import Event


class LocationIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200)
    address: str = Field(min_length=1, max_length=300)
    city: str = Field(min_length=1, max_length=120)
    lat: float | None = Field(default=None, ge=-90, le=90)
    lng: float | None = Field(default=None, ge=-180, le=180)


class EventCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=10_000)
    important_information: str = Field(default="", max_length=2_000)
    starts_at: AwareDatetime
    ends_at: AwareDatetime
    places: int = Field(ge=1, le=100_000)
    price_cents: int = Field(ge=0, le=10_000_000)
    currency: str = Field(default="EUR", min_length=3, max_length=3)
    location: LocationIn


class EventUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=10_000)
    important_information: str | None = Field(default=None, max_length=2_000)
    starts_at: AwareDatetime | None = None
    ends_at: AwareDatetime | None = None
    places: int | None = Field(default=None, ge=1, le=100_000)
    price_cents: int | None = Field(default=None, ge=0, le=10_000_000)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    location: LocationIn | None = None


class CoverUploadRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    content_type: str
    content_length: int = Field(gt=0)


class CoverAttach(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str = Field(min_length=1, max_length=300)


def location_out(event: Event) -> dict[str, Any]:
    loc = event.location
    return {
        "name": loc.name,
        "address": loc.address,
        "city": loc.city,
        "lat": loc.point.lat,
        "lng": loc.point.lng,
    }


def event_out(event: Event, cover_url: str | None = None) -> dict[str, Any]:
    return {
        "id": str(event.id),
        "organizer_id": event.organizer_id,
        "title": event.title,
        "description": event.description,
        "important_information": event.important_information,
        "cover_picture_key": event.cover_picture_key,
        "cover_picture_url": cover_url,
        "starts_at": event.starts_at.isoformat(),
        "ends_at": event.ends_at.isoformat(),
        "places": event.places,
        "price_cents": event.price.amount_cents,
        "currency": event.price.currency,
        "is_free": event.price.is_free,
        "status": str(event.status),
        "location": location_out(event),
        "created_at": event.created_at.isoformat(),
        "updated_at": event.updated_at.isoformat(),
        "published_at": event.published_at.isoformat() if event.published_at else None,
        "cancelled_at": event.cancelled_at.isoformat() if event.cancelled_at else None,
    }
