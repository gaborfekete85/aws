# Payments

Stripe Checkout (test mode) for paid Bookings.

- `BookingRequested` (paid) → a Checkout Session with the Booking id in `metadata` / `client_reference_id`, Stripe idempotency key `checkout-<booking_id>`.
- Stripe rejects session expiries closer than 30 minutes, while a Hold lasts 15. The session is created with Stripe's minimum and **expired actively on `HoldExpired`**, so the payable window never outlives the Hold.
- `GET /bookings/{booking_id}/checkout` → `202 {status: creating}` while the consumer is still working, then `{url, expires_at}`; owner or Admin only.

## Manual setup (per environment)

Terraform creates `CHANGE_ME` placeholders (write-only; real values never enter Terraform state). Replace them with `aws ssm put-parameter --overwrite --type SecureString` for:

| Parameter | Value |
|---|---|
| `/localbini/<env>/stripe/secret_key` | Stripe **test** secret key (Dashboard → Developers → API keys) |
| `/localbini/<env>/stripe/webhook_secret` | signing secret of the webhook endpoint created in #26 |
