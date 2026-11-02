# PostgreSQL for the Catalog, DynamoDB for Bookings

Events and Locations live in PostgreSQL (SQLAlchemy ORM + PostGIS) because the Catalog is relational and needs "within X km, between dates" queries. Bookings and Holds live in DynamoDB because overbooking is prevented with conditional writes on a per-Event place counter, and expired Holds are released through TTL. OpenSearch was rejected on cost; geo + date search is served by PostGIS.

## Consequences

- No cross-store transactions: the Booking service reads Event places/price from Catalog events (EventBridge), never by joining.
- Lambdas talking to RDS run inside the VPC; Booking Lambdas do not need to.
