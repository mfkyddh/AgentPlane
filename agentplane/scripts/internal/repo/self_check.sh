#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
cd "$repo_root"
if [[ -z "${UV_PROJECT_ENVIRONMENT:-}" ]]; then
  export UV_PROJECT_ENVIRONMENT="$repo_root/.venv-wsl"
fi

# Phase 4 / Lane 6 contract:
# projection verification / fixture / ledger remain scenario-specific workflows.
# do not move them into the daily thin gate.
uv run python -m pytest \
  tests/test_docs_no_legacy_terms.py \
  tests/test_wsl_first_docs.py \
  tests/test_repo_snapshot_contracts.py \
  tests/test_onepanel_plugin_and_skills.py \
  tests/test_app_onboarding_standard.py \
  -q
