#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
cd "$repo_root"
. .codex/environments/lib/guard-host-workspace.sh
agentplane_guard_host_workspace "$repo_root"

# Phase 4 / Lane 6 contract:
# projection verification / fixture / ledger remain scenario-specific workflows.
# do not move them into the daily thin gate.
uv run python -m pytest \
  tests/repository/test_docs_no_legacy_terms.py \
  tests/host/test_wsl_first_docs.py \
  tests/repository/test_repo_snapshot_contracts.py \
  tests/onepanel/test_onepanel_plugin_and_skills.py \
  tests/app/test_app_onboarding_standard.py \
  -q
