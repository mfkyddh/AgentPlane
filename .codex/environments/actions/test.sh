#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/../../.."
uv run python -m pytest tests/test_app_onboarding_standard.py tests/test_docs_no_legacy_terms.py tests/test_onepanel_plugin_and_skills.py -q
