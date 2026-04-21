#!/usr/bin/env bash
set -euo pipefail

agentplane_guard_host_workspace() {
  local repo_root="${1:-$PWD}"
  local resolved
  resolved="$(cd "$repo_root" && pwd -P)"

  case "${WSL_DISTRO_NAME:-}:$resolved" in
    ?*:/mnt/[A-Za-z]|?*:/mnt/[A-Za-z]/*)
      {
        printf 'AgentPlane forbids running WSL/Linux automation from a Windows-mounted checkout: %s\n' "$resolved"
        printf 'Use the host-native checkout with its single .venv, or clone a separate checkout under the Linux filesystem.\n'
      } >&2
      exit 2
      ;;
  esac
}
