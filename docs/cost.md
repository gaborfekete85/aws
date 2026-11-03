# Cost and performance review

Region `eu-central-1`, list prices as of late 2026 (approximate; check the AWS pricing pages before quoting). Traffic assumption for **dev**: a handful of people, < 100k API requests and < 1k emails per month. Everything not listed below stays inside the free tier or rounds to cents.

## Summary

| | Before review | After review | With the shared database (#39) |
|---|---|---|---|
| **dev**, fixed monthly cost | **≈ USD 43** (over the USD 40 budget) | **≈ USD 18** | **≈ USD 10** |
| Catalog Lambda package | 39 MB (zip) | 22 MB | |
| Catalog cold invoke (local arm64 runtime) | ≈ 3.2 s | ≈ 2.6 s | |
| Web entry chunk | 508 kB (157 kB gzip) | 274 kB (87 kB gzip) | |

## Monthly cost model (dev)

| Item | Before | After | Change |
|---|---|---|---|
| RDS PostgreSQL `db.t4g.micro` single-AZ (≈ USD 0.018/h) | 13.1 (24×7) | 5.1 (07–20 h weekdays) | EventBridge Scheduler stops it outside office hours |
| RDS gp3 storage 20 GB (billed while stopped) | 2.7 | 2.7 | n/a |
| Interface VPC endpoints: Secrets Manager + EventBridge, 1 AZ (USD 0.012/h each) | 17.5 | 0 | removed in dev: the NAT instance already gives egress |
| NAT instance `t4g.nano` + its public IPv4 (USD 0.005/h) | 7.6 | 7.6 | needed anyway for the geocoder (#15) |
| Secrets Manager (RDS-managed secret) | 0.4 | 0.4 | n/a |
| Lambda, API Gateway, DynamoDB, SQS, EventBridge, SES, Cognito, CloudFront, S3, Amplify Hosting, X-Ray, CloudWatch Logs | ≈ 2 | ≈ 2 | free tiers / cents at dev traffic |
| **Total** | **≈ 43** | **≈ 18** | **−58 %** |

The S3 and DynamoDB **gateway** endpoints are free and stay.

### Dev on a shared, existing database (#39)

Dev can skip its own RDS instance and put the Catalog on an existing PostgreSQL that is already paid for (the owner's `database-1`, PostgreSQL 18 on a `db.t4g.micro` in eu-north-1). That removes the RDS rows above (5.1 + 2.7) but keeps a USD 0.4 secret for the dedicated login: **≈ USD 7.8 less, dev ≈ USD 10/month**. Cross-region traffic (USD 0.02/GB) rounds to zero at dev volume.

- **How**: set `external_db_host` and `external_db_security_group_id` for `infra/envs/dev` (GitHub secrets `DEV_EXTERNAL_DB_HOST`, `DEV_EXTERNAL_DB_SG_ID`; never committed, the repo is public). Run `scripts/setup_external_db.sh` first: it creates the `meeton_dev` role and database, enables PostGIS with the master user and writes the `meeton-dev-catalog-db` secret. Without those variables dev creates its own RDS as before; prod always does.
- **Network**: the in-VPC Lambdas leave through the NAT instance, which now has an Elastic IP; dev adds one ingress rule on the database's security group for exactly that `/32` (Terraform-managed, so `destroy` removes it). TLS (`sslmode=require`) on the wire.
- **Isolation**: a separate database owned by a separate login, `CONNECTION LIMIT 20`, `statement_timeout 15s`, `idle_in_transaction_session_timeout 60s`, and `CONNECT` revoked from `PUBLIC`, so dev cannot starve or read the instance's other databases. It does share CPU, memory and disk with them.
- **Cost of it**: ≈ 25 ms per query round trip Frankfurt–Stockholm (a search ≈ 50 ms slower, a cold start ≈ 100 ms more for the TLS handshake); fine for dev, not for prod.
- **Verified**: the Catalog suite (104 tests) on PostgreSQL 18.6 + PostGIS 3.6 through the restricted `meeton_dev` login; RDS 18.3-R2 ships PostGIS 3.6.3 (AWS extension table).
- **Remove**: `terraform destroy` for dev, then `scripts/setup_external_db.sh --drop`. Budgets alert at 80 % actual and 100 % forecast (USD 40 dev, USD 120 prod).

### Prod (not changed; recommendation)

Multi-AZ RDS (≈ 26 + storage), NAT Gateway (≈ 38 + USD 0.052/GB), 2 interface endpoints × 2 AZs (≈ 35), public IPv4 (≈ 4): **≈ USD 110/month fixed**, uncomfortably close to its USD 120 budget. At low traffic the interface endpoints cost more than routing that traffic through the NAT Gateway (USD 0.052/GB), so **dropping them in prod too would save ≈ USD 35/month**. Keep them only if a no-internet-path requirement appears. Left as a decision for the owner; it is one line in `infra/envs/prod/main.tf` (`interface_endpoints = []`).

## Compute: Lambda

**arm64 everywhere**: `lambda-service` hard-codes `architectures = ["arm64"]` (≈ 20 % cheaper per GB-s than x86, typically faster for Python); the NAT instance is `t4g`, RDS is `db.t4g`.

**Measured locally** (`scripts/measure_lambdas.py`): each zip runs in the official `public.ecr.aws/lambda/python:3.13-arm64` image; cold = first invoke incl. imports, warm = median of 5; memory = container RSS (slightly *over*-states, it includes the runtime emulator):

| Function | Package | Cold (ms) | Warm (ms) | Memory (MB) | Configured |
|---|---|---|---|---|---|
| health | 8 MB | 697 | 1.6 | 55 | 128 |
| catalog-api (search) | **39 → 22 MB** | **3190 → 2632** | 14.5 → 17.3 | **131 → 112** | **1024** |
| booking-api (availability) | 8 MB | 1179 | 7.3 | 69 | 512 |
| booking-expiry (sweep) | 8 MB | 839 | 5.7 | 56 | 256 |
| payments-api | 11 MB | 652 | 1.8 | 61 | 256 |
| notifications (SQS) | 8 MB | 582 | 2.3 | 50 | 256 |
| identity-api | 8 MB | 619 | 2.0 | 56 | 256 |

Why these sizes: every function uses < 120 MB, so memory is chosen for **CPU** (Lambda allocates CPU proportionally; 1,769 MB = 1 vCPU). The user-facing **Catalog** API is import-bound on cold starts (SQLAlchemy, geoalchemy2, psycopg), so it gets 1,024 MB; the hot Booking path 512 MB; background consumers 256 MB (latency-insensitive). At dev traffic the cost difference is cents: the busiest function, the expiry sweep, runs 43,200 × 256 MB × ≈ 50 ms ≈ 540 GB-s per month, ≈ USD 0.007.

**Biggest win, the Catalog package**: profiling imports (`python -X importtime`) and the zip showed `numpy` (53 MB unpacked) pulled in by `shapely`, used *only* to convert one Point to/from lat/lng. Replaced by a 15-line EWKB parser (`catalog.repository.parse_ewkb_point`, unit-tested; all PostGIS round-trip and radius tests unchanged) → zip −44 %, cold invoke −17 %, memory −15 %.

**Power tuning on AWS** (run once after the dev deploy, confirms the table above):

```bash
# deploys the open-source AWS Lambda Power Tuning state machine (SAR app)
aws serverlessrepo create-cloud-formation-change-set --stack-name lambda-power-tuning \
  --application-id arn:aws:serverlessrepo:us-east-1:451282441545:applications/aws-lambda-power-tuning \
  --capabilities CAPABILITY_IAM
# then for catalog-api and booking-api:
#   {"lambdaARN": "...", "powerValues": [256, 512, 1024, 1536], "num": 50, "strategy": "balanced",
#    "payload": <an HTTP API event from meeton_shared.testing.http_api_event>}
```

Remaining cold-start levers, not done yet (measure first): Provisioned Concurrency for `catalog-api` in prod only if p95 cold starts matter (it costs ≈ USD 10/month per warm 1 GB instance); `lbz` imports PyJWT/cryptography (≈ 0.5 s) for auth we do not use (API Gateway verifies JWTs).

## Data stores

**DynamoDB: on-demand, not provisioned.** Booking traffic is spiky: a popular Event opening for Booking is a burst of conditional writes on one partition, and the rest of the time it is near zero. Provisioned capacity would need to be sized for the burst (or autoscale too slowly for it) and pay for idle capacity in between; on-demand bills per request (≈ USD 1.5 per million writes) and absorbs bursts without throttling. Provisioned becomes cheaper only at sustained utilisation above ≈ 15–20 % of the provisioned capacity, which this workload will not reach soon. Revisit with real CloudWatch `ConsumedWriteCapacityUnits` data. PITR is enabled (USD 0.2 per GB-month, ≈ 0 at this size).

**RDS sizing.** `db.t4g.micro` (2 vCPU burstable, 1 GB) is the smallest Graviton class; the Catalog workload is small indexed reads (GiST + `(status, starts_at)` indexes). Watch `CPUCreditBalance` and `FreeableMemory`; move to `db.t4g.small` before considering Aurora. In dev the instance is **stopped outside 07:00–20:00 Europe/Zurich on weekdays** (`rds_office_hours_only`); the in-VPC Lambdas get a connection error while it is stopped, which is acceptable for dev. (RDS restarts a stopped instance after 7 days; the daily schedule makes that moot.)

## Logs

Every Lambda log group and the API access log group have 14-day retention (`log_retention_days`); the RDS PostgreSQL log group is now created by Terraform with the same retention (RDS would otherwise create it with *never expire*). Logs are structured JSON lines, so Logs Insights queries stay cheap and precise.

## Cost allocation tags

Every resource carries `project`, `env`, `owner` (provider `default_tags`; plan output shows them in `tags_all`). To use them in **Cost Explorer** and in the per-environment budget filter, they must be **activated** as cost allocation tags. That is now Terraform (`infra/bootstrap/cost_tags.tf`, `activate_cost_allocation_tags = true`), but AWS only accepts keys that already appear in billing data, so flip it about 24 hours after the first environment deploy. Verify with `aws ce list-cost-allocation-tags --status Active`.

## Web

Route-level code splitting (`React.lazy`) plus loading the Amplify Auth SDK on demand: the entry chunk went from **508 kB to 274 kB** (157 → 87 kB gzipped, −45 %); Organizer, Admin, Checkout, My Bookings and the auth pages are separate 0.5–6 kB chunks; Amplify (`auth` + `tokenProvider`, ≈ 140 kB) loads only when a session is checked or a user logs in. Amplify Hosting serves it from CloudFront with long-lived caching of the hashed assets.
