# Localbini

Book places at local Events. Organizers publish Events at a Location and date; Visitors find them by location and date and pay to book.

Vocabulary lives in [`GLOSSARY.md`](GLOSSARY.md), design in [`docs/architecture.md`](docs/architecture.md), decisions in [`docs/adr/`](docs/adr/).

## Layout

| Path | What |
|---|---|
| `infra/` | Terraform: `bootstrap/` (state + OIDC, applied once), `modules/`, `envs/{dev,prod}` |
| `services/shared` | Lambdalizator helpers, auth/roles, domain-event envelope, logging |
| `services/{catalog,booking,payments,notifications}` | One Lambda service per bounded context |
| `web/` | React + Vite + TypeScript + Redux Toolkit |
| `tests/` | `e2e/` (Playwright), `integration/` (pytest against dev), `smoke/` (aiohttp load) |

## Prerequisites

[uv](https://docs.astral.sh/uv/), [bun](https://bun.sh), Terraform ≥ 1.10, Docker.

## Local development

```bash
# Python (all services, one workspace)
uv sync
uv run pytest                      # unit tests
uv run ruff check . && uv run ruff format --check .
uv run mypy services

# Integration tests (Postgres/PostGIS + DynamoDB Local)
docker compose up -d
uv run pytest -m integration

# Web
cd web
bun install
bun run dev                        # http://localhost:5173
bun run test                       # Vitest
bun run lint && bun run typecheck

# Terraform
terraform -chdir=infra/envs/dev init -backend=false && terraform -chdir=infra/envs/dev validate
terraform fmt -recursive infra
(cd infra && tflint --init && tflint --recursive)   # lints every module directly

# Git hooks
uvx pre-commit install
```

## CI/CD (GitHub Actions)

| Workflow | Trigger | Does |
|---|---|---|
| `ci.yml` | every PR + push to `main` | ruff, mypy, pytest (with Postgres/PostGIS + DynamoDB Local services), eslint, tsc, Vitest, `terraform fmt -check`, `validate`, tflint |
| `terraform-plan.yml` | PRs touching infra/services | `terraform plan` for dev and prod with the read-only plan role; posts/updates one comment per env |
| `deploy.yml` | push to `main` | build Lambda zips → `apply` dev (deploys Lambda code) → post-deploy integration tests → `apply` prod after a required reviewer approves the `prod` Environment |

Per-environment `concurrency` groups (`deploy-dev`, `deploy-prod`, never cancelled mid-apply) plus S3 state locking prevent overlapping applies. Plan and deploy jobs are skipped until the bootstrap role variables exist (see `infra/bootstrap/README.md`).
