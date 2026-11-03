# Playwright UI tests

Two modes, same specs:

| Mode | How | What runs |
|---|---|---|
| **Offline** (CI on every PR) | `bunx playwright test` | builds `web/` with fake auth, serves it with `vite preview`; APIs, Nominatim, S3 and Stripe are mocked with `page.route` (`login`, `search`, `organizer`, `checkout` specs) |
| **Deployed** (after every dev deploy) | `E2E_BASE_URL=<web url> bunx playwright test --grep @dev` | `journeys.spec.ts` against real Cognito, API, S3 and **Stripe test mode** |

## Deployed journeys (`@dev`, serial, self-contained)

1. login with a real Cognito user and log out
2. Organizer creates a free and a paid Event (unique `E2E … <run id>` titles) and publishes them
3. a Visitor finds the Event in search
4. an Attendee books the free Event → "You're booked!"
5. an Attendee books the paid Event on **Stripe Checkout with test card 4242 4242 4242 4242** → confirmed via the webhook → "Confirmed" in My Bookings
6. cleanup: the Organizer cancels both Events (exercises cancellation + Attendee emails)

Traces, screenshots and the HTML/JUnit reports are uploaded as the `playwright-dev-<run>` artifact.

## One-time setup

```bash
E2E_ORGANIZER_EMAIL=... E2E_ORGANIZER_PASSWORD=... E2E_USER_EMAIL=... E2E_USER_PASSWORD=... \
  scripts/create_e2e_users.sh dev
```

Then add the same four values as GitHub Actions **secrets**. In the SES sandbox, also verify the two addresses so confirmation/cancellation emails can be delivered.
