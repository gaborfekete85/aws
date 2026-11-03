#!/usr/bin/env bash
# Create (or reset) the Cognito users the deployed E2E/integration suites log in as.
#   E2E_ORGANIZER_EMAIL=... E2E_ORGANIZER_PASSWORD=... E2E_USER_EMAIL=... E2E_USER_PASSWORD=... \
#     scripts/create_e2e_users.sh dev
# Store the same four values as GitHub Actions secrets.
set -euo pipefail
env=${1:?usage: create_e2e_users.sh <dev|prod>}
root=$(cd "$(dirname "$0")/.." && pwd)
pool=$(terraform -chdir="$root/infra/envs/$env" output -raw user_pool_id)

upsert() {
  local email=$1 password=$2 group=${3:-}
  aws cognito-idp admin-create-user --user-pool-id "$pool" --username "$email" \
    --user-attributes Name=email,Value="$email" Name=email_verified,Value=true Name=name,Value="E2E ${group:-attendee}" \
    --message-action SUPPRESS >/dev/null 2>&1 || true
  aws cognito-idp admin-set-user-password --user-pool-id "$pool" --username "$email" \
    --password "$password" --permanent
  if [[ -n "$group" ]]; then
    aws cognito-idp admin-add-user-to-group --user-pool-id "$pool" --username "$email" --group-name "$group"
  fi
  echo "ready: $email ${group:+($group)}"
}

upsert "${E2E_ORGANIZER_EMAIL:?}" "${E2E_ORGANIZER_PASSWORD:?}" organizer
upsert "${E2E_USER_EMAIL:?}" "${E2E_USER_PASSWORD:?}"
