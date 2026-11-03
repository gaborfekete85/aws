"""Public search and detail endpoints through the lbz handler (no JWT)."""

import pytest

from .conftest import ORGANIZER

pytestmark = pytest.mark.integration


def create_and_publish(call, event_body, **overrides) -> str:
    _, body = call("POST", "/events", claims=ORGANIZER, body=event_body(**overrides))
    call("POST", "/events/{event_id}/publish", claims=ORGANIZER, path={"event_id": body["id"]})
    return body["id"]


def test_visitor_searches_without_logging_in(call, event_body) -> None:
    published = create_and_publish(call, event_body)
    call("POST", "/events", claims=ORGANIZER, body=event_body(title="Still a draft"))

    status, body = call(
        "GET", "/events", query={"lat": "47.3769", "lng": "8.5417", "radius_km": "5"}
    )
    assert status == 200
    assert [e["id"] for e in body["items"]] == [published]
    assert body["items"][0]["distance_km"] == pytest.approx(0.0, abs=0.01)
    assert body["count"] == 1
    assert body["next_offset"] is None


def test_date_only_bounds_cover_whole_local_days(call, event_body) -> None:
    published = create_and_publish(call, event_body)
    _, body = call("GET", "/organizer/events", claims=ORGANIZER)
    day = body["items"][0]["starts_at"][:10]
    _, found = call("GET", "/events", query={"from": day, "to": day})
    assert [e["id"] for e in found["items"]] == [published]


@pytest.mark.parametrize(
    "query",
    [
        {"lat": "abc", "lng": "8"},
        {"lat": "47", "lng": "8", "radius_km": "0"},
        {"limit": "0"},
        {"from": "03/11/2026"},
    ],
)
def test_bad_query_is_422(call, query) -> None:
    status, body = call("GET", "/events", query=query)
    assert status == 422, body


def test_detail_shows_published_and_hides_drafts(call, event_body) -> None:
    published = create_and_publish(call, event_body)
    _, draft = call("POST", "/events", claims=ORGANIZER, body=event_body(title="Draft"))

    status, body = call("GET", "/events/{event_id}", path={"event_id": published})
    assert status == 200
    assert body["important_information"] == "Bring a blanket."
    assert body["location"]["city"] == "Zürich"
    assert call("GET", "/events/{event_id}", path={"event_id": draft["id"]})[0] == 404


def test_cancelled_event_detail_stays_visible(call, event_body) -> None:
    event_id = create_and_publish(call, event_body)
    call("POST", "/events/{event_id}/cancel", claims=ORGANIZER, path={"event_id": event_id})
    status, body = call("GET", "/events/{event_id}", path={"event_id": event_id})
    assert (status, body["status"]) == (200, "cancelled")
