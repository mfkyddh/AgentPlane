#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/../../.."
. .codex/environments/lib/guard-host-workspace.sh
agentplane_guard_host_workspace "$PWD"

uv run python -m pytest tests/app/test_app_onboarding_standard.py tests/repository/test_docs_no_legacy_terms.py tests/onepanel/test_onepanel_plugin_and_skills.py -q
