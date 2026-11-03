import pytest
from notifications import sender
from notifications.rendering import Email

EMAIL = Email(subject="Hi", html="<p>Hi</p>", text="Hi")


def test_send_once_sends_a_single_email(aws, outbox) -> None:
    assert sender.send_once("BookingConfirmed#b1", "ada@example.com", EMAIL, 2_000_000_000)
    assert not sender.send_once("BookingConfirmed#b1", "ada@example.com", EMAIL, 2_000_000_000)
    assert len(outbox()) == 1
    assert outbox()[0].destinations["ToAddresses"] == ["ada@example.com"]


def test_failed_send_releases_the_claim(aws, monkeypatch) -> None:
    def boom(*_args, **_kwargs):
        raise RuntimeError("SES down")

    real_send = sender.send
    monkeypatch.setattr(sender, "send", boom)
    with pytest.raises(RuntimeError):
        sender.send_once("k", "ada@example.com", EMAIL, 2_000_000_000)
    monkeypatch.setattr(sender, "send", real_send)
    assert sender.send_once("k", "ada@example.com", EMAIL, 2_000_000_000)  # retry works
