#!/usr/bin/env bash
# Tear down the whole dev environment (#40). See docs/teardown.md.
#
#   scripts/destroy_dev.sh             # destroy dev; keep the dev database on the shared instance
#   scripts/destroy_dev.sh --with-db   # also drop meeton_dev (database, login, secret) there
#
# Steps:
#   1. pause the Deploy workflow, otherwise the next push to main recreates dev
#   2. `terraform destroy` for infra/envs/dev (Terraform asks before deleting anything)
#   3. --with-db: scripts/setup_external_db.sh --drop (asks again)
#   4. list anything still tagged project=meeton, env=dev
#
# Needs admin AWS credentials, gh (logged in to the repo) and Docker for --with-db.
# Re-deploy later: `gh workflow enable deploy.yml` and re-run the Deploy workflow.
set -euo pipefail

root=$(cd "$(dirname "$0")/.." && pwd)
with_db=0
[[ "${1:-}" == "--with-db" ]] && with_db=1

echo "== 1/4 pausing the Deploy workflow"
gh workflow disable deploy.yml 2>/dev/null && echo "Deploy workflow disabled" ||
  echo "Deploy workflow already disabled (or gh not logged in: check before pushing to main)"

echo "== 2/4 terraform destroy (dev)"
# Terraform hashes the Lambda zips even when destroying.
for zip in shared catalog booking payments notifications identity; do
  [[ -f "$root/dist/$zip.zip" ]] || { "$root/scripts/build_all_lambdas.sh"; break; }
done
# Required inputs; their values do not matter for a destroy, so fall back to the repo's.
export TF_VAR_alert_emails=${TF_VAR_alert_emails:-$(gh variable get ALERT_EMAILS)}
export TF_VAR_sender_email=${TF_VAR_sender_email:-$(gh variable get SENDER_EMAIL)}
terraform -chdir="$root/infra/envs/dev" init -input=false >/dev/null
terraform -chdir="$root/infra/envs/dev" destroy

if [[ $with_db == 1 ]]; then
  echo "== 3/4 dropping the dev database on the shared instance"
  "$root/scripts/setup_external_db.sh" --drop
else
  echo "== 3/4 kept: database/login meeton_dev and secret meeton-dev-catalog-db (use --with-db to drop)"
fi

echo "== 4/4 leftovers tagged project=meeton, env=dev (the tagging index can lag a few minutes)"
left=0
for region in eu-central-1 eu-north-1 us-east-1; do
  arns=$(aws resourcegroupstaggingapi get-resources --region "$region" \
    --tag-filters Key=project,Values=meeton Key=env,Values=dev \
    --query 'ResourceTagMappingList[].ResourceARN' --output text)
  for arn in $arns; do
    echo "  $arn"
    left=1
  done
done
if [[ $left == 0 ]]; then
  echo "  none"
elif [[ $with_db == 0 ]]; then
  echo "  (the meeton-dev-catalog-db secret is expected without --with-db)"
fi
