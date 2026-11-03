# Booking publishes the affected Attendees when an Event is cancelled

When an Organizer cancels an Event, Notifications must email every affected Attendee (#32). Only the Booking context knows who they are. Notifications could call the Booking API or query the Bookings table, but ADR-0002 rules out synchronous calls between services, and reading another context's table couples them through its storage layout.

Instead, Booking (which consumes `EventCancelled` anyway, to cancel the Bookings) publishes **`EventBookingsCancelled`** listing the Attendees whose Bookings it just cancelled: booking id, attendee id/email, places, and whether the Booking was confirmed. Notifications consumes that and sends the emails concurrently.

## Consequences

- Attendees are chunked (200 per message, ~30 KB) to stay far below EventBridge's 256 KB limit; each message carries `part` / `parts`.
- Only Bookings that actually changed state in this delivery are listed, so a redelivered `EventCancelled` produces no second email wave.
- The Attendee email comes from the ID token at Booking time and is stored on the Booking. If Attendees could change their email, Notifications would need a Cognito lookup; not needed today.
