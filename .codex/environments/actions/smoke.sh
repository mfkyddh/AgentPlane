#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/../../.."
exec bash agentplane/scripts/internal/repo/self_check.sh
