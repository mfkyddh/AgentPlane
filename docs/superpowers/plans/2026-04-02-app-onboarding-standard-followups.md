# App Onboarding Standard Follow-up Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Finish the remaining hard enforcement work after the v1 app onboarding standard docs, Codex environment, and repo self-check landed.

**Architecture:** Keep the documentation and lightweight repo tooling already merged as the control contract, then move the remaining gaps into formal CLI behavior and hard validation. Do not expand compat behavior; replace it with single formal paths and enforcement checks.

**Tech Stack:** Markdown docs, Python CLI under `ops/cli`, shell helpers under `ops/scripts/internal`, existing pytest contract tests.

---

## Summary

This plan covers only the work that is still not fully solved after `docs: add app onboarding standard v1`.

The current branch already completed:

- App onboarding reference docs
- Compact root `AGENTS.md`
- `.codex/environments/` bootstrap and actions
- Repo self-check entrypoint
- Contract tests for the new onboarding standard

This follow-up plan covers the remaining gaps:

- `environment.toml` schema is still based on conservative inference, not a field-perfect official sample
- rollback-state behavior is documented, but not enforced in formal deploy code
- compat retirement is documented, but not enforced
- naming registry exists, but is not validated automatically
- long-lived docs still contain stale absolute `.worktrees` paths in historical assets
- document lifecycle metadata is not standardized yet

## Task 1: Lock Codex Environment Contract To Current Official Schema

**Files:**
- Modify: `.codex/environments/environment.toml`
- Modify: `.codex/environments/setup/setup.sh`
- Modify: `.codex/environments/actions/*.sh`
- Test: `tests/test_app_onboarding_standard.py`

- [ ] **Step 1: Re-read the current official local environments docs and compare every field used in `environment.toml`**

Run: `python - <<'PY'\nfrom pathlib import Path\np = Path('.codex/environments/environment.toml')\nprint(p.read_text())\nPY`

Expected: the current TOML content is printed for comparison against the official docs.

- [ ] **Step 2: Adjust the TOML field names only if the official docs differ from the current inferred layout**

Rule: keep the script entrypoint names stable; only change TOML surface fields if the official schema requires it.

- [ ] **Step 3: Keep setup thin and actions thin**

Requirement:
- setup remains idempotent, lightweight, secret-free
- actions continue to delegate to repo-owned scripts
- no production deploy or rollback action is added to Codex top-bar actions

- [ ] **Step 4: Re-run the onboarding contract test**

Run: `uv run pytest tests/test_app_onboarding_standard.py -q`

Expected: PASS

## Task 2: Enforce Rollback-State Behavior In Formal App Delivery

**Files:**
- Modify: `ops/cli/apps.py`
- Modify: `ops/domain/app/*` as needed by the current deploy substrate
- Modify: `docs/architecture/op-linux-app-collaboration.md`
- Test: `tests/test_app_cli.py`

- [ ] **Step 1: Identify the exact formal deploy and rollback path used by `app delivery deploy` and `app delivery rollback`**

Run: `rg -n "deploy --dry-run|rollback --dry-run|app delivery deploy|app delivery rollback|render-runtime" ops tests`

Expected: the formal app delivery entrypoints and supporting implementation files are located.

- [ ] **Step 2: Add a formal rollback-state model**

Minimum required behavior:
- capture the last known-good runtime before cutover
- create the rollback-state container before traffic cutover
- verify candidate runtime before cutover
- on cutover failure, switch back immediately
- only delete the old runtime after post-cutover verification plus observation window

- [ ] **Step 3: Add tests for both failure points**

Required scenarios:
- cutover-precheck failure leaves old runtime untouched
- post-cutover verification failure switches back to rollback state

- [ ] **Step 4: Run the focused delivery tests**

Run: `uv run pytest tests/test_app_cli.py -q -k "deploy or rollback or delivery"`

Expected: PASS

## Task 3: Turn Compat Retirement Ledger Into Enforcement

**Files:**
- Modify: `ops/scripts/internal/repo/self_check.sh`
- Create or modify: `tests/test_repo_snapshot_contracts.py`
- Create or modify: `tests/test_docs_no_legacy_terms.py`
- Modify: `docs/reference/compat-retirement-ledger.md`

- [ ] **Step 1: Define what is enforceable now**

Enforce only what is objective:
- active docs must not present compat entrypoints as default
- compat entries listed in the ledger must have a replacement and last_verified date
- self-check must include the compat enforcement tests

- [ ] **Step 2: Add the ledger checks to tests**

Required assertions:
- each ledger row has `compat_entry`, `replacement`, `last_verified`, `remove_when`, `removal_test`
- each listed compat entry still exists if not yet removed
- no active doc re-promotes a compat entry to default status

- [ ] **Step 3: Run the focused compat/document tests**

Run: `uv run pytest tests/test_docs_no_legacy_terms.py tests/test_repo_snapshot_contracts.py -q`

Expected: PASS

## Task 4: Turn Naming Registry Into Contract Validation

**Files:**
- Modify: `docs/reference/control-plane-naming-registry.md`
- Modify: `ops/cli/apps.py`
- Modify: `tests/test_app_cli.py`

- [ ] **Step 1: Pick the minimum enforceable naming rules**

Enforce only stable rules first:
- `app_id`
- `inventory.service_key`
- image name family
- prod container suffix `-prod`
- dev container suffix `-dev`

- [ ] **Step 2: Validate naming during contract checks**

Requirement:
- invalid naming should fail at `app delivery validate-contract`
- do not postpone naming mismatches until deploy time

- [ ] **Step 3: Add focused contract tests**

Run: `uv run pytest tests/test_app_cli.py -q -k "validate_contract or container_name or service_key"`

Expected: PASS

## Task 5: Standardize Long-Lived Docs And Remove Stale Worktree Paths From Active Layers

**Files:**
- Modify: `README.md`
- Modify: `docs/architecture/README.md`
- Modify: `docs/maintainers/control-plane-authoring.md`
- Modify: active runbooks as needed
- Test: `tests/test_docs_no_legacy_terms.py`

- [ ] **Step 1: Define the scope**

Rule:
- `README`, `architecture`, `reference`, and active runbooks should not hardcode historical `.worktrees` absolute paths
- `history` and `handoff` may keep them, but only as execution snapshots

- [ ] **Step 2: Add a focused test for active-layer `.worktrees` path leakage**

Run: `rg -n "/root/work/OP_Linux/.worktrees/" README.md docs/architecture docs/reference docs/runbooks`

Expected: no matches in active layers after cleanup.

- [ ] **Step 3: Re-run doc contract tests**

Run: `uv run pytest tests/test_docs_no_legacy_terms.py -q`

Expected: PASS

## Task 6: Add Document Lifecycle Metadata To Long-Term Docs

**Files:**
- Modify: `docs/architecture/*.md`
- Modify: `docs/reference/*.md`
- Modify: `docs/maintainers/control-plane-authoring.md`
- Create or modify: doc metadata test if needed

- [ ] **Step 1: Pick a minimal metadata set**

Required fields:
- `status`
- `owner`
- `last_verified`
- `superseded_by`

- [ ] **Step 2: Apply metadata only to long-term docs first**

Scope:
- architecture
- reference
- maintainer docs

Do not try to retrofit all history docs in the same step.

- [ ] **Step 3: Add a lightweight metadata contract test**

Run: `uv run pytest tests/test_docs_no_legacy_terms.py -q`

Expected: PASS or extend with a dedicated metadata test if needed.

## Task 7: Keep Repo Self-Check As The Single Daily Gate

**Files:**
- Modify: `ops/scripts/internal/repo/self_check.sh`
- Modify: `README.md`
- Modify: `.codex/environments/actions/smoke.sh`

- [ ] **Step 1: Expand self-check only with stable, fast contract tests**

Keep:
- docs contract tests
- skills catalog tests
- onboarding standard tests

Avoid:
- slow environment-specific checks
- host-specific live operations

- [ ] **Step 2: Make README and Codex actions point to the same gate**

Requirement:
- `README` and `Smoke` action must both route to the same self-check script
- no duplicate competing daily check command should be introduced

- [ ] **Step 3: Run the self-check end to end**

Run: `bash ops/scripts/internal/repo/self_check.sh`

Expected: PASS

## Test Plan

- `uv run pytest tests/test_app_onboarding_standard.py -q`
- `uv run pytest tests/test_docs_no_legacy_terms.py tests/test_repo_snapshot_contracts.py -q`
- `uv run pytest tests/test_app_cli.py -q -k "deploy or rollback or delivery or validate_contract or container_name or service_key"`
- `bash ops/scripts/internal/repo/self_check.sh`

## Assumptions

- No compat-first fallback work will be added in this phase.
- The next phase should prefer hard validation in formal CLI code over more documentation.
- `history` and archived docs may keep historical absolute paths; active layers should not.
- If OpenAI later publishes a stricter `environment.toml` schema, the file may change, but the script entrypoint names should remain stable.
