# Release expired Holds with a scheduled sweep, not DynamoDB TTL

A Hold keeps Places for an Attendee in Checkout for 15 minutes (`HOLD_MINUTES`). DynamoDB TTL deletes expired items lazily ("typically within a few days"), so TTL + Streams would leave Places locked for hours or days. Instead an EventBridge schedule runs `booking.expiry.handle` **every minute**. It queries a sparse GSI (`gsi3`, Hold items only, sorted by logical expiry) and expires each due Hold in **one transaction**:

1. delete the Hold, only if it still exists;
2. give its Places back to the counter;
3. move the Booking `pending → expired`, only if it is still pending.

Deleting the Hold is the exactly-once guard: a parallel sweep or a payment that converted the Hold first makes the transaction fail harmlessly. A payment arriving after expiry finds no Hold and is flagged for manual handling (#27; refunds are out of scope).

TTL stays on Hold items set to expiry + 24 h, purely as garbage collection; it can never pre-empt the sweep.

## Consequences

- At most ~1 minute of extra Hold time; Stripe Checkout sessions expire no later than the Hold (#25), so Attendees cannot pay long after expiry.
- `gsi3` has a single partition key (`HOLD`). Fine for this platform's volume (Holds live 15 minutes); shard the key (`HOLD#<n>`) if write throughput ever approaches partition limits.
- Cost: 43,200 tiny Lambda invocations per month (~free tier).
