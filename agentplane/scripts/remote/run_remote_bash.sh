#!/usr/bin/env bash
set -euo pipefail

# Historical wrapper for shell callers. Formal entrypoint is `uv run python -m agentplane.cli host remote bash ...`.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

usage() {
  cat <<'EOF' >&2
Usage:
  run_remote_bash.sh <host-alias> [--script-file <linux-path>] [-- <arg>...]

Notes:
  - Wrapper only. Formal entrypoint: uv run python -m agentplane.cli host remote bash ...
  - Prefer --script-file when the current shell is not already in WSL.
  - Without --script-file, the script body is read from stdin and sent to remote bash.
  - Extra args after -- become $1..$N inside the remote bash script.
EOF
}

if [[ $# -lt 1 ]]; then
  usage
  exit 1
fi

host="$1"
shift || true

script_file=""
if [[ $# -gt 0 && "$1" == "--script-file" ]]; then
  if [[ $# -lt 2 ]]; then
    usage
    exit 1
  fi
  script_file="$2"
  shift 2
fi

if [[ $# -gt 0 && "$1" == "--" ]]; then
  shift
fi

cmd=(python3 -m agentplane.cli host remote bash "$host" --repo-root "$REPO_ROOT")
if [[ -n "$script_file" ]]; then
  cmd+=(--script-file "$script_file")
fi
if [[ $# -gt 0 ]]; then
  cmd+=(-- "$@")
fi

cd "$REPO_ROOT"
exec "${cmd[@]}"
