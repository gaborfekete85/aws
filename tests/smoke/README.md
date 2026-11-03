# Smoke / load test (asyncio + aiohttp)

`load.py` creates a free Event (or uses `--event-id`), fires N concurrent searches and M concurrent Booking attempts at that one Event, then asserts **no overbooking** (`confirmed ≤ places` and `places_left == places − confirmed`) and reports p50/p90/p95/p99/max latency per operation. Exit code 1 on overbooking, error rate above `--max-error-rate`, or p95 above `--p95-budget-ms`.

- **Against dev, on demand**: Actions → *Smoke / load test* → Run workflow (inputs: searches, bookings, places, concurrency). The JSON report is uploaded as an artifact.
- **Locally**, against the real Catalog + Booking handlers (`scripts/local_api.py`: process pool, local event bus, fake authorizer):

```bash
docker compose up -d
export DATABASE_URL=postgresql+psycopg://meeton:meeton@localhost:5432/catalog DYNAMODB_ENDPOINT_URL=http://localhost:8000
uv run python scripts/local_api.py --port 4010 &
uv run python tests/smoke/load.py --base-url http://localhost:4010 \
  --organizer-token local:org-load:organizer --attendee-token local:attendee-load \
  --searches 200 --bookings 60 --places 20 --concurrency 30
```

First local run (2026-11-03, 8 worker processes): 60 concurrent Booking attempts on 20 places → **20 confirmed, 40 × 409, places_left 0, no overbooking**; 0 errors; search p50 243 ms / p95 492 ms, booking p50 107 ms / p95 217 ms (laptop, PostGIS under amd64 emulation).
