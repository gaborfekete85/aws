"""Organizer Event management API: end to end through the lbz handler (Postgres + moto bus)."""

import pytest

from .conftest import ADMIN, ATTENDEE, ORGANIZER, OTHER_ORGANIZER

pytestmark = pytest.mark.integration


def create(call, event_body, claims=ORGANIZER, **overrides):
    status, body = call("POST", "/events", claims=claims, body=event_body(**overrides))
    assert status == 201, body
    return body


def test_organizer_creates_a_draft_with_geocoded_location(call, event_body, sent_events) -> None:
    body = create(call, event_body)
    assert body["status"] == "draft"
    assert body["organizer_id"] == "org-1"
    assert body["location"]["lat"] == pytest.approx(47.3769)
    assert body["important_information"] == "Bring a blanket."
    assert sent_events() == []  # Drafts are private: nothing on the bus


def test_explicit_coordinates_skip_geocoding(call, event_body) -> None:
    loc = {"name": "Pin", "address": "Somewhere 1", "city": "Atlantis", "lat": 46.5, "lng": 6.6}
    body = create(call, event_body, location=loc)
    assert (body["location"]["lat"], body["location"]["lng"]) == (46.5, 6.6)


def test_unknown_address_is_a_422_with_the_field(call, event_body) -> None:
    loc = {"name": "X", "address": "Nowhere 1", "city": "Atlantis"}
    status, body = call("POST", "/events", claims=ORGANIZER, body=event_body(location=loc))
    assert status == 422
    assert body["field"] == "address"


def test_invalid_body_is_422(call, event_body) -> None:
    status, body = call("POST", "/events", claims=ORGANIZER, body=event_body(places=0))
    assert status == 422
    assert body["errors"][0]["loc"] == ["places"]


def test_domain_invariant_violation_is_422(call, event_body) -> None:
    body = event_body()
    body["ends_at"] = body["starts_at"]
    status, _ = call("POST", "/events", claims=ORGANIZER, body=body)
    assert status == 422


@pytest.mark.parametrize(("claims", "status"), [(None, 401), (ATTENDEE, 403)])
def test_only_organizers_create(call, event_body, claims, status) -> None:
    assert call("POST", "/events", claims=claims, body=event_body())[0] == status


def test_publish_emits_event_published_with_places_and_price(call, event_body, sent_events) -> None:
    event_id = create(call, event_body)["id"]
    status, body = call(
        "POST", "/events/{event_id}/publish", claims=ORGANIZER, path={"event_id": event_id}
    )
    assert status == 200
    assert body["status"] == "published"
    [(type_, detail)] = sent_events()
    assert type_ == "EventPublished"
    assert detail["type"] == "EventPublished"
    assert detail["source"] == "localbini.catalog"
    assert detail["data"]["event_id"] == event_id
    assert detail["data"]["places"] == 40
    assert detail["data"]["price_cents"] == 2500
    assert detail["data"]["currency"] == "CHF"


def test_edit_draft_does_not_emit_but_edit_published_does(call, event_body, sent_events) -> None:
    event_id = create(call, event_body)["id"]
    path = {"event_id": event_id}
    status, body = call(
        "PATCH", "/events/{event_id}", claims=ORGANIZER, path=path, body={"places": 50}
    )
    assert (status, body["places"]) == (200, 50)
    assert sent_events() == []

    call("POST", "/events/{event_id}/publish", claims=ORGANIZER, path=path)
    status, body = call(
        "PATCH",
        "/events/{event_id}",
        claims=ORGANIZER,
        path=path,
        body={"places": 60, "price_cents": 3000},
    )
    assert status == 200
    [(type_, detail)] = sent_events()
    assert type_ == "EventUpdated"
    assert detail["data"]["places"] == 60
    assert detail["data"]["price_cents"] == 3000
    assert detail["data"]["changed"] == ["places", "price"]


def test_cancel_emits_event_cancelled(call, event_body, sent_events) -> None:
    event_id = create(call, event_body)["id"]
    path = {"event_id": event_id}
    call("POST", "/events/{event_id}/publish", claims=ORGANIZER, path=path)
    status, body = call("POST", "/events/{event_id}/cancel", claims=ORGANIZER, path=path)
    assert (status, body["status"]) == (200, "cancelled")
    [(type_, detail)] = sent_events()
    assert type_ == "EventCancelled"
    assert detail["data"]["cancelled_at"]


def test_illegal_transition_is_409_and_nothing_is_emitted(call, event_body, sent_events) -> None:
    event_id = create(call, event_body)["id"]
    status, _ = call(
        "POST", "/events/{event_id}/cancel", claims=ORGANIZER, path={"event_id": event_id}
    )
    assert status == 409
    assert sent_events() == []


def test_other_organizer_gets_403_on_every_action(call, event_body) -> None:
    event_id = create(call, event_body)["id"]
    path = {"event_id": event_id}
    assert (
        call("PATCH", "/events/{event_id}", claims=OTHER_ORGANIZER, path=path, body={"places": 2})[
            0
        ]
        == 403
    )
    assert call("POST", "/events/{event_id}/publish", claims=OTHER_ORGANIZER, path=path)[0] == 403
    assert call("POST", "/events/{event_id}/cancel", claims=OTHER_ORGANIZER, path=path)[0] == 403
    assert call("GET", "/organizer/events/{event_id}", claims=OTHER_ORGANIZER, path=path)[0] == 403


def test_admin_can_act_on_any_event(call, event_body, sent_events) -> None:
    event_id = create(call, event_body)["id"]
    path = {"event_id": event_id}
    assert call("POST", "/events/{event_id}/publish", claims=ADMIN, path=path)[0] == 200
    assert (
        call("PATCH", "/events/{event_id}", claims=ADMIN, path=path, body={"title": "Admin fix"})[0]
        == 200
    )
    assert call("POST", "/events/{event_id}/cancel", claims=ADMIN, path=path)[0] == 200
    assert [t for t, _ in sent_events()] == ["EventCancelled"]


def test_list_mine_filters_by_owner_and_status(call, event_body) -> None:
    mine = create(call, event_body)["id"]
    published = create(call, event_body, title="Second")["id"]
    create(call, event_body, claims=OTHER_ORGANIZER, title="Not mine")
    call("POST", "/events/{event_id}/publish", claims=ORGANIZER, path={"event_id": published})

    status, body = call("GET", "/organizer/events", claims=ORGANIZER)
    assert status == 200
    assert {e["id"] for e in body["items"]} == {mine, published}

    _, body = call("GET", "/organizer/events", claims=ORGANIZER, query={"status": "published"})
    assert [e["id"] for e in body["items"]] == [published]


def test_admin_lists_another_organizers_events_but_organizer_cannot(call, event_body) -> None:
    create(call, event_body)
    _, body = call("GET", "/organizer/events", claims=ADMIN, query={"organizer_id": "org-1"})
    assert len(body["items"]) == 1
    status, _ = call(
        "GET", "/organizer/events", claims=OTHER_ORGANIZER, query={"organizer_id": "org-1"}
    )
    assert status == 403


def test_unknown_event_is_404(call) -> None:
    path = {"event_id": "00000000-0000-0000-0000-000000000000"}
    assert call("POST", "/events/{event_id}/publish", claims=ORGANIZER, path=path)[0] == 404
    assert (
        call("POST", "/events/{event_id}/publish", claims=ORGANIZER, path={"event_id": "nope"})[0]
        == 404
    )
