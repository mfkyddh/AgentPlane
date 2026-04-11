# App V1 Real Catalog Aftercare Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the first real tracked app catalog entry for `sub2api` without widening `app v1` scope or mixing runtime projection into catalog truth.

**Architecture:** Freeze the first real onboarding scope in docs, then add tests that pin the exact real catalog shape and its `app object` resolution behavior, and only then replace the empty sample in `inventory/apps/catalog.json`. Keep all runtime facts in existing contract and inventory layers.

**Tech Stack:** Python stdlib tests, existing `ops.cli app` entrypoints, tracked JSON inventory, Markdown specs/plans

---

### Task 1: Freeze Aftercare Scope In Docs

**Files:**
- Create: `docs/superpowers/specs/2026-04-02-app-v1-real-catalog-aftercare-design.md`
- Create: `docs/superpowers/plans/2026-04-02-app-v1-real-catalog-aftercare.md`

- [ ] **Step 1: Write the aftercare design freeze**
- [ ] **Step 2: Write the implementation plan**

### Task 2: Write Failing Tests For The First Real Catalog

**Files:**
- Modify: `tests/test_app_object_cli.py`

- [ ] **Step 1: Add a test that freezes `inventory/apps/catalog.json` to one real `sub2api` entry with `prod0-main` and `prod2-main` only**
- [ ] **Step 2: Run the focused test and confirm it fails against the current empty sample**
- [ ] **Step 3: Add a test that runs `app object search` against the real repo and asserts `prod0-main` returns `sub2api`**
- [ ] **Step 4: Run the focused test and confirm it fails because the real catalog is still empty**
- [ ] **Step 5: Add a test that runs `app object search` against the real repo and asserts `prod2-main` returns `sub2api` while `wsl` stays empty**
- [ ] **Step 6: Run the focused test and confirm it fails because the real catalog is still empty**

### Task 3: Replace The Empty Sample With The Real Entry

**Files:**
- Modify: `inventory/apps/catalog.json`

- [ ] **Step 1: Replace the empty `apps` array with the real `sub2api` entry**
- [ ] **Step 2: Re-run the focused catalog and object-search tests and confirm they pass**

### Task 4: Run Minimal CLI Verification

**Files:**
- Reference: `inventory/apps/catalog.json`
- Reference: `/root/work/sub2api/deploy/op/contract.yaml`
- Reference: `/root/work/sub2api/deploy/op/contract.prod2.yaml`

- [ ] **Step 1: Run `uv run pytest -q tests/test_app_object_cli.py`**
- [ ] **Step 2: Run `uv run python -m ops.cli app object search --target prod0-main --repo-root /root/work/OP_Linux/.worktrees/codex-cli-first-repo-refactor`**
- [ ] **Step 3: Run `uv run python -m ops.cli app object search --target prod2-main --repo-root /root/work/OP_Linux/.worktrees/codex-cli-first-repo-refactor`**
- [ ] **Step 4: Run `uv run python -m ops.cli app object search --target wsl --repo-root /root/work/OP_Linux/.worktrees/codex-cli-first-repo-refactor`**
- [ ] **Step 5: Run `uv run python -m ops.cli app delivery validate-contract --target prod0-main --app sub2api --repo-root /root/work/OP_Linux/.worktrees/codex-cli-first-repo-refactor`**
- [ ] **Step 6: Run `uv run python -m ops.cli app delivery validate-contract --target prod2-main --app sub2api --repo-root /root/work/OP_Linux/.worktrees/codex-cli-first-repo-refactor`**
