"""Catalog domain invariants and Event status transitions (no database)."""

from datetime import UTC, datetime, timedelta

import pytest

from catalog.domain import (
    EventStatus,
    GeoPoint,
    IllegalStatusTransition,
    Location,
    Money,
)
from localbini_shared.errors import ConflictError, ValidationError

NOW = datetime(2026, 11, 3, 12, 0, tzinfo=UTC)


class TestInvariants:
    def test_new_event_is_draft(self, make_event) -> None:
        assert make_event().status is EventStatus.DRAFT

    @pytest.mark.parametrize("title", ["", "   ", "x" * 121])
    def test_title_required_and_bounded(self, make_event, title) -> None:
        with pytest.raises(ValidationError):
            make_event(title=title)

    def test_must_end_after_start(self, make_event) -> None:
        start = NOW + timedelta(days=1)
        with pytest.raises(ValidationError, match="end after"):
            make_event(starts_at=start, ends_at=start)

    @pytest.mark.parametrize("places", [0, -3])
    def test_needs_at_least_one_place(self, make_event, places) -> None:
        with pytest.raises(ValidationError, match="place"):
            make_event(places=places)

    def test_naive_datetimes_are_rejected(self, make_event) -> None:
        with pytest.raises(ValidationError, match="timezone"):
            make_event(starts_at=datetime(2030, 1, 1), ends_at=datetime(2030, 1, 2))

    def test_money(self) -> None:
        assert Money(0).is_free
        assert not Money(100, "EUR").is_free
        with pytest.raises(ValidationError):
            Money(-1)
        with pytest.raises(ValidationError):
            Money(100, "XYZ")

    @pytest.mark.parametrize(("lat", "lng"), [(91, 0), (-91, 0), (0, 181), (0, -181)])
    def test_geo_point_bounds(self, lat, lng) -> None:
        with pytest.raises(ValidationError):
            GeoPoint(lat, lng)

    def test_location_fields_required(self) -> None:
        with pytest.raises(ValidationError):
            Location(name="", address="a", city="c", point=GeoPoint(0, 0))


class TestStatusTransitions:
    def test_draft_to_published(self, make_event) -> None:
        event = make_event(starts_at=NOW + timedelta(days=1))
        event.publish(now=NOW)
        assert event.status is EventStatus.PUBLISHED
        assert event.published_at == NOW

    def test_published_to_cancelled(self, make_event) -> None:
        event = make_event(starts_at=NOW + timedelta(days=1))
        event.publish(now=NOW)
        event.cancel(now=NOW)
        assert event.status is EventStatus.CANCELLED
        assert event.cancelled_at == NOW

    def test_draft_cannot_be_cancelled(self, make_event) -> None:
        with pytest.raises(IllegalStatusTransition):
            make_event().cancel(now=NOW)

    def test_published_cannot_be_published_again(self, make_event) -> None:
        event = make_event(starts_at=NOW + timedelta(days=1))
        event.publish(now=NOW)
        with pytest.raises(IllegalStatusTransition):
            event.publish(now=NOW)

    def test_cancelled_is_terminal(self, make_event) -> None:
        event = make_event(starts_at=NOW + timedelta(days=1))
        event.publish(now=NOW)
        event.cancel(now=NOW)
        for move in (event.publish, event.cancel):
            with pytest.raises(IllegalStatusTransition):
                move(now=NOW)

    def test_illegal_transition_is_a_conflict(self, make_event) -> None:
        with pytest.raises(ConflictError):
            make_event().cancel(now=NOW)

    def test_cannot_publish_an_event_that_already_started(self, make_event) -> None:
        event = make_event(starts_at=NOW - timedelta(minutes=1))
        with pytest.raises(ValidationError, match="already started"):
            event.publish(now=NOW)


class TestEdit:
    def test_edit_returns_changed_fields(self, make_event) -> None:
        event = make_event()
        assert event.edit(now=NOW, title="New title", places=40) == {"title"}
        assert event.title == "New title"
        assert event.updated_at == NOW

    def test_edit_is_all_or_nothing(self, make_event) -> None:
        event = make_event()
        with pytest.raises(ValidationError):
            event.edit(title="Fine", places=0)
        assert event.title == "Sunset jazz on the lake"
        assert event.places == 40

    def test_cannot_edit_unknown_or_protected_fields(self, make_event) -> None:
        with pytest.raises(ValidationError):
            make_event().edit(status=EventStatus.PUBLISHED)
        with pytest.raises(ValidationError):
            make_event().edit(organizer_id="someone-else")

    def test_cancelled_event_cannot_be_edited(self, make_event) -> None:
        event = make_event(starts_at=NOW + timedelta(days=1))
        event.publish(now=NOW)
        event.cancel(now=NOW)
        with pytest.raises(ConflictError):
            event.edit(title="x")

    def test_published_event_cannot_move_into_the_past(self, make_event) -> None:
        event = make_event(starts_at=NOW + timedelta(days=1))
        event.publish(now=NOW)
        past = NOW - timedelta(days=1)
        with pytest.raises(ValidationError, match="past"):
            event.edit(now=NOW, starts_at=past, ends_at=past + timedelta(hours=1))
