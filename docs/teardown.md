# Teardown

Everything Meeton creates in AWS can be removed again. There are three layers, and each is removed separately on purpose. Remove them in this order.

| Layer | What | How it is removed | Cost while kept |
|---|---|---|---|
| **dev** | everything in `infra/envs/dev` (VPC, NAT, Lambdas, API, Cognito, DynamoDB, SQS, EventBridge, S3 media + CloudFront, Amplify, SES identity, budget, SSM parameters, the security group rule on the shared database) | `scripts/destroy_dev.sh` | ≈ USD 10/month |
| **dev data on the shared database** | database and login `meeton_dev` on `database-1`, secret `meeton-dev-catalog-db` | `scripts/destroy_dev.sh --with-db` | ≈ USD 0.4/month (the secret) |
| **bootstrap** | Terraform state bucket, CI roles `meeton-gha-plan` / `meeton-gha-deploy`, permissions boundary | manual, below (the state bucket is protected on purpose) | cents |

## Destroy dev

```bash
scripts/destroy_dev.sh            # or --with-db to also drop the dev database on database-1
```

1. **Pauses the Deploy workflow.** It runs on every push to `main` and would otherwise recreate dev with the next commit.
2. **Runs `terraform destroy`.** Terraform lists everything it will delete and waits for `yes`. Expect 10–20 minutes; AWS takes that long to release the network interfaces of the in-VPC Lambdas.
3. **Drops the dev database on the shared instance (`--with-db` only).** It asks for confirmation and the master password.
4. **Lists anything still tagged `project=meeton, env=dev`.** The tagging index can lag a few minutes behind.

Nothing in dev blocks this:
- Deletion protection is off in dev for Cognito and DynamoDB, and for RDS when dev has its own instance.
- The media bucket is deleted with its pictures (`force_destroy` outside prod).
- Every log group is created by Terraform, so none is left behind.

The pre-existing GitHub OIDC provider is only looked up, never created, so it stays.

**Lost with a destroy:** all data (Events, Bookings, Cover pictures, users including the Admin), the Google/Stripe values in SSM, and the SES verification clicks. Setup steps 5–8 must be repeated after a redeploy (see `infra/bootstrap/README.md` and the service READMEs).

**Deploy again:**

```bash
gh workflow enable deploy.yml
gh workflow run deploy.yml       # or push to main
```

## Destroy prod

Prod has deletion protection on Cognito, DynamoDB and RDS, and RDS takes a final snapshot. To remove prod deliberately:
1. Set those protections off in `infra/modules/stack` for prod and apply.
2. Run `terraform -chdir=infra/envs/prod destroy`.

Delete the final snapshot afterwards if you do not need it.

## Remove the bootstrap (last)

Only after dev (and prod) are destroyed: their state lives in this bucket.

```bash
# 1. allow deleting the versioned state bucket: in infra/bootstrap/state.tf
#    remove `lifecycle { prevent_destroy = true }` and add `force_destroy = true`
terraform -chdir=infra/bootstrap apply      # records force_destroy
terraform -chdir=infra/bootstrap destroy
# 2. GitHub side (optional)
gh variable delete AWS_PLAN_ROLE_ARN; gh variable delete AWS_DEPLOY_ROLE_ARN; gh variable delete TF_STATE_BUCKET
gh secret delete DEV_EXTERNAL_DB_HOST; gh secret delete DEV_EXTERNAL_DB_SG_ID
```

Do not commit the `state.tf` change: the protection is what keeps a stray `destroy` from deleting every environment's state.
