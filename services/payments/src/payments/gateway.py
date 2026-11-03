"""Stripe behind a small port, so the domain logic is testable without Stripe."""

from __future__ import annotations

import contextlib
import os
from dataclasses import dataclass
from functools import cache
from typing import Any, Protocol

import boto3
import stripe

# Stripe rejects Checkout Session expiries closer than 30 minutes.
STRIPE_MIN_EXPIRY_SECONDS = 30 * 60


@dataclass(frozen=True)
class CheckoutSession:
    id: str
    url: str
    expires_at: int  # epoch seconds


@dataclass(frozen=True)
class CheckoutRequest:
    booking_id: str
    event_id: str
    event_title: str
    places: int
    unit_amount_cents: int
    currency: str
    customer_email: str | None
    expires_at: int
    success_url: str
    cancel_url: str


class PaymentGateway(Protocol):
    def create_checkout(self, request: CheckoutRequest) -> CheckoutSession: ...

    def expire_checkout(self, session_id: str) -> None: ...

    def verify_webhook(self, payload: bytes, signature: str | None) -> dict[str, Any]: ...


@cache
def _secret(param_name: str) -> str:
    value: str = boto3.client("ssm").get_parameter(Name=param_name, WithDecryption=True)[
        "Parameter"
    ]["Value"]
    return value


class StripeGateway:
    """Stripe test-mode client; keys come from SSM SecureString parameters."""

    def __init__(self, api_key: str | None = None, webhook_secret: str | None = None) -> None:
        self._api_key = api_key
        self._webhook_secret = webhook_secret

    @property
    def client(self) -> stripe.StripeClient:
        key = self._api_key or _secret(os.environ["STRIPE_SECRET_KEY_PARAM"])
        return stripe.StripeClient(key)

    def create_checkout(self, request: CheckoutRequest) -> CheckoutSession:
        session = self.client.v1.checkout.sessions.create(
            params=self.session_params(request),
            # Retried BookingRequested deliveries reuse the same session.
            options={"idempotency_key": f"checkout-{request.booking_id}"},
        )
        return CheckoutSession(id=session.id, url=str(session.url), expires_at=session.expires_at)

    @staticmethod
    def session_params(request: CheckoutRequest) -> Any:
        params: dict[str, Any] = {
            "mode": "payment",
            "client_reference_id": request.booking_id,
            "line_items": [
                {
                    "quantity": request.places,
                    "price_data": {
                        "currency": request.currency.lower(),
                        "unit_amount": request.unit_amount_cents,
                        "product_data": {"name": request.event_title or "Event"},
                    },
                }
            ],
            "metadata": {"booking_id": request.booking_id, "event_id": request.event_id},
            "payment_intent_data": {"metadata": {"booking_id": request.booking_id}},
            "expires_at": request.expires_at,
            "success_url": request.success_url,
            "cancel_url": request.cancel_url,
        }
        if request.customer_email:
            params["customer_email"] = request.customer_email
        return params

    def expire_checkout(self, session_id: str) -> None:
        with contextlib.suppress(stripe.InvalidRequestError):  # already expired / completed
            self.client.v1.checkout.sessions.expire(session_id)

    def verify_webhook(self, payload: bytes, signature: str | None) -> dict[str, Any]:
        secret = self._webhook_secret or _secret(os.environ["STRIPE_WEBHOOK_SECRET_PARAM"])
        event = stripe.Webhook.construct_event(payload, signature, secret)
        result: dict[str, Any] = event.to_dict()
        return result
