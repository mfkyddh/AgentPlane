#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <host-alias> [command...]" >&2
  exit 1
fi

host="$1"
shift || true

SSH_CONFIG="$(python3 "$REPO_ROOT/agentplane/ssh.py" --repo-root "$REPO_ROOT" config-path)"
connection_target="$(python3 "$REPO_ROOT/agentplane/ssh.py" --repo-root "$REPO_ROOT" connection-target "$host")"

exec ssh -F "$SSH_CONFIG" "$connection_target" "$@"
