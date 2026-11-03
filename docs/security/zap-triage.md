# OWASP ZAP findings: triage

`.github/workflows/zap.yml` scans **dev** every Monday (and on demand):

- **Baseline** (passive, plus the AJAX spider) against the web app on Amplify.
- **API scan** (active) driven by `docs/openapi.yaml`; `tests/contract` keeps that spec identical to the routes Terraform deploys.

Reports (HTML + JSON) are uploaded as the `zap-reports-<run>` artifact. `scripts/zap_gate.py` fails the job on any **High** risk alert that is not triaged in `.zap/triaged.json`. Medium and lower are reviewed here.

## Triaged findings

| Plugin | Alert | Risk | Decision | Why |
|---|---|---|---|---|
| 10049 | Non-Storable Content | Informational | Accept | Seen in the first local baseline (2026-11-03, against `vite preview`). API responses intentionally send `Cache-Control: no-store`. |
| 10055 | CSP: style-src unsafe-inline | Medium | Accept (WARN) | React applies inline `style` attributes (e.g. the Cover picture placeholder). Scripts are strictly `'self'`, which is where CSP matters most. Revisit if styles move to classes only. |
| 10098 | Cross-Domain Misconfiguration | Medium | Ignore | The API's CORS allows only the known web origins (Amplify + localhost in dev), derived in Terraform. ZAP flags any `Access-Control-Allow-Origin` response. |

## Controls already in place (why many rules pass)

- **Web (Amplify custom headers)**: `Content-Security-Policy` (no inline scripts, `frame-ancestors 'none'`, `object-src 'none'`, explicit `connect-src` / `form-action`), `Strict-Transport-Security`, `X-Content-Type-Options`, `X-Frame-Options: DENY`, `Referrer-Policy`, `Permissions-Policy`.
- **API**: every response carries `X-Content-Type-Options: nosniff`, `Cache-Control: no-store` and HSTS. JWT authorizer on every non-public route, fail-closed in Terraform. Domain-level role/owner checks behind it. Pydantic `extra="forbid"` request models.
- **Webhook**: Stripe signature verified over the raw body; replay window 5 minutes.
- **Storage**: S3 buckets private (CloudFront OAC only), TLS-only policies, presigned uploads limited by signed content type and length.

## Local run

```bash
cd web && bun run build:fake && bunx vite preview --port 4173 --host &
docker run --rm -v "$PWD/zap:/zap/wrk:rw" ghcr.io/zaproxy/zaproxy:stable \
  zap-baseline.py -t http://host.docker.internal:4173 -J zap-local.json -I
python3 scripts/zap_gate.py zap/zap-local.json
```

First local result (2026-11-03): **PASS 67, WARN 1 (Informational 10049), FAIL 0**. Note that `vite preview` does not send the Amplify headers; the dev scan checks those.
