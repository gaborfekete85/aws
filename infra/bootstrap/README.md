# Bootstrap: Terraform state and GitHub OIDC roles

Applied **once, by hand**, with local state. Everything else in `infra/` uses the bucket it creates as its backend (see ADR-0003).

## What it creates

- **State bucket** `localbini-tfstate-<account-id>`: versioning, SSE (AES256), all public access blocked, bucket-owner-enforced, TLS-only bucket policy, noncurrent versions expire after 90 days, `prevent_destroy`.
- **`localbini-gha-plan` role**: trusted for `pull_request` and `main` of this repo. `ReadOnlyAccess`, read-only on `envs/*` state, write only on `envs/*.tflock`, and an explicit deny on data-plane reads (DynamoDB items, SQS messages, secret values, log events, non-state S3 objects).
- **`localbini-gha-deploy` role**: trusted only for `main` and the `dev` / `prod` GitHub Environments, with `ref == refs/heads/main` required as well.
  - Name-scoped services (Lambda, DynamoDB, SQS, EventBridge, Logs, SSM, Secrets Manager, S3) are limited to `localbini-*` resources.
  - **Privilege-escalation guard**: it can create roles or grant them permissions only with the `localbini-workload-boundary` permissions boundary attached, can attach only project policies or the Lambda-managed execution policies, cannot touch the CI roles, state policies or the boundary itself, cannot remove a boundary, cannot rewrite trust policies after creation (no `iam:UpdateAssumeRolePolicy`; change one by recreating the role or as admin), and can pass roles only to workload services (`iam:PassedToService`).
  - Explicit deny on changing the state bucket's policy, versioning, encryption, public-access block or lifecycle, and on deleting state object versions.
- **`localbini-workload-boundary`**: the ceiling for every application role. Data access is limited to `localbini-{dev,prod}-*` resources, KMS only via SSM/Secrets Manager/SQS/S3, and the state bucket is explicitly denied. Every `aws_iam_role` in `infra/modules` sets `permissions_boundary` to it.
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

In GitHub → Settings → Environments create `dev` and `prod`, each with **Deployment branches: `main` only**; `prod` also gets a required reviewer.

Then in GitHub → Settings → Secrets and variables → Actions → **Variables**:

| Variable | Value |
|---|---|
| `AWS_PLAN_ROLE_ARN` | `terraform output -raw plan_role_arn` |
| `AWS_DEPLOY_ROLE_ARN` | `terraform output -raw deploy_role_arn` |
| `TF_STATE_BUCKET` | `terraform output -raw state_bucket` |

Keep `terraform.tfstate` from this directory somewhere safe (it is gitignored). It is small and only needed to change the bootstrap later; losing it means importing the resources again.
