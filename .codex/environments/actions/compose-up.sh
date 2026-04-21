#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/../../.."
. .codex/environments/lib/guard-host-workspace.sh
agentplane_guard_host_workspace "$PWD"

service="${SERVICE:-}"
if [[ -z "$service" ]]; then
  echo "Set SERVICE=<name> to start a repository-managed compose stack."
  find infra/compose -maxdepth 2 -name 'docker-compose.wsl.yml' | sed 's#^#- #'
  exit 0
fi

compose_file="infra/compose/$service/docker-compose.wsl.yml"
if [[ ! -f "$compose_file" ]]; then
  echo "Missing $compose_file" >&2
  exit 1
fi

docker compose -f "$compose_file" up -d
