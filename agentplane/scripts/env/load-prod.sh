#!/usr/bin/env bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
ENV_FILE="$REPO_ROOT/secrets/env/prod-jump.env"

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
  echo "Use: source $REPO_ROOT/agentplane/scripts/env/load-prod.sh" >&2
  exit 1
fi

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Missing $ENV_FILE" >&2
  return 1
fi

# shellcheck disable=SC1090
source "$ENV_FILE"
