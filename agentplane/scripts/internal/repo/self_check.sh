#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
cd "$repo_root"

# Phase 4 / Lane 6 contract:
# projection verification / fixture / ledger remain scenario-specific workflows.
# do not move them into the daily thin gate.
#
# Daily thin gate: unit + integration tests only.
# E2E and live gate tests are excluded by default.
uv run python -m pytest -m "unit or integration" -q
