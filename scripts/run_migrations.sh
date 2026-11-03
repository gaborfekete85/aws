#!/usr/bin/env bash
# Invoke the in-VPC migrate Lambda for an environment and fail on error.
#   scripts/run_migrations.sh dev
set -euo pipefail
env=${1:?usage: run_migrations.sh <dev|prod>}
root=$(cd "$(dirname "$0")/.." && pwd)
fn=$(terraform -chdir="$root/infra/envs/$env" output -raw catalog_migrate_function)
out=$(mktemp)
meta=$(aws lambda invoke --function-name "$fn" --cli-read-timeout 310 \
  --payload '{"revision":"head"}' --cli-binary-format raw-in-base64-out "$out")
cat "$out"; echo
if echo "$meta" | grep -q FunctionError; then
  echo "migration failed: $meta" >&2
  exit 1
fi
