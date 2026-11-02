#!/usr/bin/env bash
# Build every service zip into dist/.
set -euo pipefail
root=$(cd "$(dirname "$0")/.." && pwd)
for dir in "$root"/services/*/; do
  "$root/scripts/build_lambda.sh" "$(basename "$dir")"
done
