"""Payments HTTP API: the web app fetches the Checkout URL for a Booking."""

from __future__ import annotations

from lbz.response import Response
from lbz.router import add_route

from meeton_shared.api import ApiResource, domain_errors, make_http_handler
from payments.checkout import checkout_for
from payments.webhook import process


class PaymentsResource(ApiResource):
    @add_route("/bookings/{booking_id}/checkout", method="GET")
    @domain_errors
    def checkout(self, booking_id: str) -> Response:
        record = checkout_for(self.principal, booking_id)
        if record is None:
            # BookingRequested is processed asynchronously; the web app polls.
            return Response({"status": "creating", "retry_after_ms": 500}, status_code=202)
        return Response(
            {"status": record.status, "url": record.url, "expires_at": record.expires_at}
        )

    @add_route("/payments/stripe/webhook", method="POST")
    @domain_errors
    def stripe_webhook(self) -> Response:
        raw = self.request.raw_body
        payload = raw if isinstance(raw, bytes) else b""
        result = process(payload, self.request.headers.get("Stripe-Signature"))
        return Response({"received": True, "duplicate": result.duplicate})


handle = make_http_handler(PaymentsResource, "payments")
