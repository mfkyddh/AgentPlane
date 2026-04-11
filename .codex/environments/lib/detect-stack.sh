#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"

has_python=0
has_node=0

if [[ -f "$repo_root/pyproject.toml" ]]; then
  has_python=1
fi

if [[ -f "$repo_root/package.json" ]]; then
  has_node=1
fi

printf 'REPO_ROOT=%s\n' "$repo_root"
printf 'HAS_PYTHON=%s\n' "$has_python"
printf 'HAS_NODE=%s\n' "$has_node"
