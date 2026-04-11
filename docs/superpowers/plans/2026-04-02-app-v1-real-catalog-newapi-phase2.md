# App V1 Real Catalog NewAPI Phase 2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `newapi` as the second real tracked app catalog entry and sync the corresponding `app object` and tracked `apps` ledgers without entering any app runtime surface.

**Architecture:** Freeze the second-phase scope in docs, then add failing tests that pin the exact real catalog shape, `newapi` object resolution, delivery contract resolution, and tracked ledgers. After the red phase, apply the minimal data-only changes in tracked JSON/Markdown artifacts so the existing `app` handlers resolve `newapi` through the catalog without code-path expansion.

**Tech Stack:** Python stdlib tests, existing `ops.cli app` command surface, tracked JSON catalog and ledgers, Markdown specs/plans

---

### Task 1: Freeze The Phase 2 Scope

**Files:**
- Create: `docs/superpowers/specs/2026-04-02-app-v1-real-catalog-newapi-phase2-design.md`
- Create: `docs/superpowers/plans/2026-04-02-app-v1-real-catalog-newapi-phase2.md`

- [ ] **Step 1: Write the phase 2 design freeze**
- [ ] **Step 2: Write the implementation plan freeze**

### Task 2: Add Failing Tests For The Real `newapi` Catalog Entry

**Files:**
- Modify: `tests/test_app_object_cli.py`

- [ ] **Step 1: Freeze `inventory/apps/catalog.json` to exactly two real entries: `sub2api` and `newapi`**
- [ ] **Step 2: Run the focused catalog-shape test and confirm it fails while the tracked catalog still only contains `sub2api`**
- [ ] **Step 3: Add a failing test for `app object get --target prod0-main --app newapi`**
- [ ] **Step 4: Run the focused prod0 test and confirm it fails because `newapi` is not yet in tracked catalog**
- [ ] **Step 5: Add a failing test for `app object get --target prod2-main --app newapi` and `wsl` remaining empty**
- [ ] **Step 6: Run the focused prod2/wsl test and confirm it fails because `newapi` is not yet in tracked catalog**
- [ ] **Step 7: Add a failing test for `app delivery validate-contract --target prod0-main/prod2-main --app newapi`**
- [ ] **Step 8: Run the focused validate-contract test and confirm it fails because catalog resolution does not yet include `newapi`**
- [ ] **Step 9: Add a failing test that freezes tracked `prod0-main` and `prod2-main` `apps` ledgers to include `newapi`**
- [ ] **Step 10: Run the focused ledger test and confirm it fails while tracked ledgers still only list `sub2api`**

### Task 3: Apply The Minimal Tracked Data Changes

**Files:**
- Modify: `inventory/apps/catalog.json`
- Modify: `inventory/servers/prod0-main/ledgers/apps.json`
- Modify: `inventory/servers/prod0-main/ledgers/apps.md`
- Modify: `inventory/servers/prod2-main/ledgers/apps.json`
- Modify: `inventory/servers/prod2-main/ledgers/apps.md`

- [ ] **Step 1: Add the real `newapi` entry to `inventory/apps/catalog.json`**
- [ ] **Step 2: Update `prod0-main` tracked `apps` ledgers to include `newapi`**
- [ ] **Step 3: Update `prod2-main` tracked `apps` ledgers to include `newapi`**
- [ ] **Step 4: Re-run the focused tests and confirm they pass**

### Task 4: Run Minimal Verification

**Files:**
- Reference: `inventory/apps/catalog.json`
- Reference: `inventory/servers/prod0-main/ledgers/apps.json`
- Reference: `inventory/servers/prod2-main/ledgers/apps.json`

- [ ] **Step 1: Run `uv run python -m pytest tests/test_app_object_cli.py -q`**
- [ ] **Step 2: Run `uv run python -m ops.cli app object search --target prod0-main --repo-root /root/work/OP_Linux/.worktrees/codex-cli-first-repo-refactor`**
- [ ] **Step 3: Run `uv run python -m ops.cli app object get --target prod0-main --app newapi --repo-root /root/work/OP_Linux/.worktrees/codex-cli-first-repo-refactor`**
- [ ] **Step 4: Run `uv run python -m ops.cli app object search --target prod2-main --repo-root /root/work/OP_Linux/.worktrees/codex-cli-first-repo-refactor`**
- [ ] **Step 5: Run `uv run python -m ops.cli app object get --target prod2-main --app newapi --repo-root /root/work/OP_Linux/.worktrees/codex-cli-first-repo-refactor`**
- [ ] **Step 6: Run `uv run python -m ops.cli app object search --target wsl --repo-root /root/work/OP_Linux/.worktrees/codex-cli-first-repo-refactor`**
- [ ] **Step 7: Run `uv run python -m ops.cli app delivery validate-contract --target prod0-main --app newapi --repo-root /root/work/OP_Linux/.worktrees/codex-cli-first-repo-refactor`**
- [ ] **Step 8: Run `uv run python -m ops.cli app delivery validate-contract --target prod2-main --app newapi --repo-root /root/work/OP_Linux/.worktrees/codex-cli-first-repo-refactor`**
