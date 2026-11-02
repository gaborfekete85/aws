# Terraform state in S3 with native locking, deployed by GitHub Actions via OIDC

Remote state lives in a versioned, encrypted S3 bucket with `use_lockfile = true` (Terraform ≥ 1.10) for concurrent-run protection instead of a DynamoDB lock table, which is now deprecated in the S3 backend. The bucket and the GitHub OIDC deploy role are created by a separate `infra/bootstrap` root applied once by hand. `dev` and `prod` share one AWS account (`eu-central-1`) with separate state keys. CI uses GitHub Actions rather than GitLab (as named in the job spec) because the code lives on GitHub.
