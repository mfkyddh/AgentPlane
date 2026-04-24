#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
eval "$("$script_dir/../lib/detect-stack.sh")"
. "$script_dir/../lib/guard-host-workspace.sh"

agentplane_guard_host_workspace "$REPO_ROOT"
cd "$REPO_ROOT"

if [[ "$HAS_PYTHON" == "1" ]]; then
  uv sync --dev
fi

if [[ "$HAS_NODE" == "1" ]]; then
  if [[ -f pnpm-lock.yaml ]]; then
    pnpm install --frozen-lockfile
  else
    pnpm install
  fi
fi

if compgen -G "infra/compose/*/docker-compose.wsl.yml" >/dev/null; then
  docker compose version >/dev/null
fi

if [[ -n "${WSL_DISTRO_NAME:-}" ]]; then
  echo "Linux backend: WSL (${WSL_DISTRO_NAME})"
  echo "Formal local infra inspect: uv run python -m agentplane.cli infra local inspect"
fi

echo "setup complete: $REPO_ROOT"
