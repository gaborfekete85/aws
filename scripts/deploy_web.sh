#!/usr/bin/env bash
# Build web/ with the environment's Terraform outputs and publish it to Amplify Hosting.
#   scripts/deploy_web.sh dev
set -euo pipefail
env=${1:?usage: deploy_web.sh <dev|prod>}
root=$(cd "$(dirname "$0")/.." && pwd)
tf() { terraform -chdir="$root/infra/envs/$env" output -raw "$1"; }

app_id=$(tf amplify_app_id)
cat > "$root/web/.env.production.local" <<ENV
VITE_API_URL=$(tf api_endpoint)
VITE_COGNITO_USER_POOL_ID=$(tf user_pool_id)
VITE_COGNITO_CLIENT_ID=$(tf web_client_id)
VITE_COGNITO_DOMAIN=$(tf hosted_ui_domain)
VITE_WEB_URL=$(tf web_url)
VITE_AUTH_MODE=amplify
ENV

(cd "$root/web" && bun install --frozen-lockfile && bun run build)
zip_file=$(mktemp -d)/web.zip
(cd "$root/web/dist" && zip -qr "$zip_file" .)

read -r job_id upload_url < <(aws amplify create-deployment --app-id "$app_id" --branch-name main \
  --query '[jobId, zipUploadUrl]' --output text)
curl --fail --silent --show-error -X PUT -H "Content-Type: application/zip" --data-binary "@$zip_file" "$upload_url"
aws amplify start-deployment --app-id "$app_id" --branch-name main --job-id "$job_id" >/dev/null

for _ in $(seq 1 60); do
  status=$(aws amplify get-job --app-id "$app_id" --branch-name main --job-id "$job_id" \
    --query 'job.summary.status' --output text)
  case "$status" in
    SUCCEED) echo "web deployed: $(tf web_url)"; exit 0 ;;
    FAILED|CANCELLED) echo "web deployment $status" >&2; exit 1 ;;
  esac
  sleep 5
done
echo "timed out waiting for Amplify job $job_id" >&2
exit 1
