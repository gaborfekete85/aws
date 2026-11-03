import pytest
from jinja2 import UndefinedError
from notifications.rendering import format_money, format_when, render


def test_renders_subject_html_and_text() -> None:
    email = render("_smoke", {"name": "Ada", "note": "See you there"})
    assert email.subject == "Hello from Localbini: Ada"
    assert "<p>Hi Ada,</p>" in email.html
    assert email.text.startswith("Hi Ada,")


def test_html_is_escaped_but_text_is_not() -> None:
    email = render("_smoke", {"name": "Ada", "note": "<script>alert(1)</script> & co"})
    assert "<script>" not in email.html
    assert "&lt;script&gt;" in email.html
    assert "<script>alert(1)</script> & co" in email.text


def test_subject_is_a_single_line() -> None:
    email = render("_smoke", {"name": "Ada\r\nBcc: victim@example.com", "note": ""})
    assert "\n" not in email.subject and "\r" not in email.subject


def test_missing_variables_fail_loudly() -> None:
    with pytest.raises(UndefinedError):
        render("_smoke", {"name": "Ada"})


def test_filters() -> None:
    assert format_when("2031-06-01T16:00:00+00:00") == "Sunday 1 June 2031, 18:00"  # Zürich time
    assert format_money(2500, "CHF") == "CHF 25.00"
    assert format_money(0, "CHF") == "Free"
