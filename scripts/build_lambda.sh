#!/usr/bin/env bash
# Build a Lambda deployment zip for one service (arm64, Python 3.13).
#   scripts/build_lambda.sh <service>      -> dist/<service>.zip
# Works from macOS or Linux: wheels are resolved for manylinux_2_28 aarch64
# (python3.13 Lambda runs Amazon Linux 2023, glibc 2.34).
set -euo pipefail

service=${1:?usage: build_lambda.sh <shared|catalog|booking|payments|notifications>}
root=$(cd "$(dirname "$0")/.." && pwd)
out="$root/dist"
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT

pkg="meeton-$service"
mkdir -p "$out" "$work/pkg"

uv export --project "$root" --package "$pkg" --no-dev --no-hashes --frozen --no-emit-workspace \
  --format requirements-txt -o "$work/requirements.txt" >/dev/null

uv pip install --quiet --target "$work/pkg" \
  --python-platform aarch64-manylinux_2_28 --python-version 3.13 --only-binary :all: \
  -r "$work/requirements.txt"

# Workspace packages (shared + the service itself) are pure Python: copy sources.
cp -R "$root/services/shared/src/meeton_shared" "$work/pkg/"
if [[ "$service" != "shared" ]]; then
  cp -R "$root/services/$service/src/$service" "$work/pkg/"
fi

# boto3/botocore ship with the Lambda runtime; drop them to keep the zip small.
rm -rf "$work/pkg"/boto3* "$work/pkg"/botocore* "$work/pkg"/s3transfer* "$work/pkg"/bin
find "$work/pkg" -name '__pycache__' -type d -prune -exec rm -rf {} +

# Deterministic zip (stable mtimes) so Terraform's source hash only changes with content.
find "$work/pkg" -exec touch -h -t 202001010000 {} +
rm -f "$out/$service.zip"
(cd "$work/pkg" && find . -type f | LC_ALL=C sort | zip -q -X -@ "$out/$service.zip")
echo "$out/$service.zip ($(du -h "$out/$service.zip" | cut -f1))"
