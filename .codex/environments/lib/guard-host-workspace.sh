#!/usr/bin/env bash
set -euo pipefail

agentplane_guard_host_workspace() {
  local repo_root="${1:-$PWD}"
  local resolved
  resolved="$(cd "$repo_root" && pwd -P)"
  printf 'AgentPlane single-checkout workspace: %s\n' "$resolved" >/dev/null
}
