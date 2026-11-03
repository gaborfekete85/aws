#!/usr/bin/env bash
# fmt + init + validate every root, and terraform test every module with tests/.
set -euo pipefail
root=$(cd "$(dirname "$0")/.." && pwd)
terraform fmt -recursive -check "$root/infra"
for r in bootstrap envs/dev envs/prod; do
  terraform -chdir="$root/infra/$r" init -backend=false -input=false >/dev/null
  terraform -chdir="$root/infra/$r" validate -no-color >/dev/null && echo "validate ok: $r"
done
for d in "$root"/infra/modules/*/; do
  if [[ -d "$d/tests" ]]; then
    terraform -chdir="$d" init -backend=false -input=false >/dev/null
    terraform -chdir="$d" test -no-color | tail -1 | sed "s|^|test $(basename "$d"): |"
  fi
done
