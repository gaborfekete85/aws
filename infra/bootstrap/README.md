# Bootstrap: Terraform state and GitHub OIDC roles

Applied **once, by hand**, with local state. Everything else in `infra/` uses the bucket it creates as its backend (see ADR-0003).

## What it creates

- **State bucket** `localbini-tfstate-<account-id>`: versioning, SSE (AES256), all public access blocked, bucket-owner-enforced, TLS-only bucket policy, noncurrent versions expire after 90 days, `prevent_destroy`.
- **`localbini-gha-plan` role**: trusted for `pull_request` and `main` of this repo; `ReadOnlyAccess` + read/write on `envs/*` state objects (needed for the lock file).
- **`localbini-gha-deploy` role**: trusted only for `main` and the `dev` / `prod` GitHub Environments; service-scoped permissions, IAM limited to `localbini-*` roles/policies, explicit deny on tampering with the state bucket.
- The GitHub OIDC provider is looked up (the account already has one). In a fresh account set `create_github_oidc_provider = true`.

## Locking

Environment backends use S3 native locking (`use_lockfile = true`, Terraform ≥ 1.10). Terraform writes `<key>.tflock` next to the state with a conditional `PutObject`; a second concurrent `plan`/`apply` fails with `Error acquiring the state lock` until the first finishes. No DynamoDB lock table.

To see it: run `terraform -chdir=infra/envs/dev apply` in one shell and, while it waits at the prompt, `terraform -chdir=infra/envs/dev plan` in another.

## One-time procedure

```bash
aws sts get-caller-identity            # admin credentials for the target account
cd infra/bootstrap
terraform init
terraform apply
terraform output                       # note the three outputs
```

Then in GitHub → Settings → Secrets and variables → Actions → **Variables**:

| Variable | Value |
|---|---|
| `AWS_PLAN_ROLE_ARN` | `terraform output -raw plan_role_arn` |
| `AWS_DEPLOY_ROLE_ARN` | `terraform output -raw deploy_role_arn` |
| `TF_STATE_BUCKET` | `terraform output -raw state_bucket` |

Keep `terraform.tfstate` from this directory somewhere safe (it is gitignored). It is small and only needed to change the bootstrap later; losing it means importing the resources again.
