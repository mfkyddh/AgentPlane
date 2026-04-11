# 1Panel App Lifecycle Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a repository-owned 1Panel app lifecycle CLI and skill that enforce `zqf_network` for `prod0-main` and WSL test environments.

**Architecture:** Keep one Python CLI as the execution truth under `ops/scripts/onepanel/`, split reusable concerns into target resolution, signed API access, and Compose policy normalization, then add a project skill and runbook that force future 1Panel operations through the CLI. Verify behavior with small stdlib `unittest` coverage before implementation.

**Tech Stack:** Python 3 standard library, existing 1Panel signed API env conventions, repository Markdown docs, Codex project skills

---

### Task 1: Write Spec And Plan Assets

**Files:**
- Create: `docs/superpowers/specs/2026-03-25-1panel-app-lifecycle-design.md`
- Create: `docs/superpowers/plans/2026-03-25-1panel-app-lifecycle.md`

- [ ] **Step 1: Write the approved design into the spec file**
- [ ] **Step 2: Write the execution plan with exact file ownership and verification steps**

### Task 2: Add Failing Compose Policy Tests

**Files:**
- Create: `tests/test_onepanel_compose_policy.py`
- Test: `tests/test_onepanel_compose_policy.py`

- [ ] **Step 1: Write tests for replacing `1panel-network` with `zqf_network`**
- [ ] **Step 2: Write tests for preserving existing extra networks while forcing `zqf_network`**
- [ ] **Step 3: Run `python3 -m unittest tests/test_onepanel_compose_policy.py -v` and confirm failure because the module does not exist yet**

### Task 3: Implement Shared 1Panel Lifecycle Modules

**Files:**
- Create: `ops/scripts/onepanel/client.py`
- Create: `ops/scripts/onepanel/env_targets.py`
- Create: `ops/scripts/onepanel/compose_policy.py`
- Modify: `ops/scripts/onepanel/api_request.py`

- [ ] **Step 1: Extract reusable env loading and request signing helpers into `client.py`**
- [ ] **Step 2: Add target resolution for `prod0-main` and WSL test environments in `env_targets.py`**
- [ ] **Step 3: Implement Compose normalization helpers in `compose_policy.py`**
- [ ] **Step 4: Refactor `api_request.py` to reuse shared client helpers without breaking current behavior**
- [ ] **Step 5: Re-run `python3 -m unittest tests/test_onepanel_compose_policy.py -v` and confirm green**

### Task 4: Implement Lifecycle CLI

**Files:**
- Create: `ops/scripts/onepanel/app_lifecycle.py`
- Modify: `ops/scripts/onepanel/client.py`
- Modify: `ops/scripts/onepanel/env_targets.py`
- Modify: `ops/scripts/onepanel/compose_policy.py`

- [ ] **Step 1: Add CLI argument parsing for `catalog get`, `install`, `reinstall`, `upgrade`, `uninstall`, `status`, and `audit-network`**
- [ ] **Step 2: Implement shared lookup helpers for app metadata, installed-app metadata, and install parameter reuse**
- [ ] **Step 3: Wire install and upgrade flows to always submit normalized Compose with `editCompose=true`**
- [ ] **Step 4: Wire reinstall and uninstall flows through the 1Panel installed-app operation endpoint**
- [ ] **Step 5: Add status and audit-network reporting that exposes container names, install ids, and network membership**
- [ ] **Step 6: Run `python3 ops/scripts/onepanel/app_lifecycle.py --help` and confirm the command tree renders**

### Task 5: Add Skill And Runbook

**Files:**
- Create: `.codex/skills/onepanel-app-lifecycle/SKILL.md`
- Create: `docs/runbooks/onepanel-app-lifecycle.md`
- Modify: `AGENTS.md`

- [ ] **Step 1: Write the project skill so future 1Panel operations route through `app_lifecycle.py`**
- [ ] **Step 2: Write the runbook with target examples for `prod0-main` and WSL**
- [ ] **Step 3: Tighten `AGENTS.md` only if a short durable rule is still missing after the new skill and runbook exist**

### Task 6: Verify On The Current Environments

**Files:**
- Modify: `inventory/servers/prod0-main/README.md`
- Modify: `inventory/servers/prod0-main/inventory.json`

- [ ] **Step 1: Run `python3 -m unittest tests/test_onepanel_compose_policy.py -v`**
- [ ] **Step 2: Run `python3 ops/scripts/onepanel/app_lifecycle.py --help`**
- [ ] **Step 3: Run `python3 ops/scripts/onepanel/app_lifecycle.py catalog get --env prod0-main --app new-api --version 0.11.8` through SSH-backed target resolution and confirm a successful response**
- [ ] **Step 4: Run `python3 ops/scripts/onepanel/app_lifecycle.py audit-network --env prod0-main` and confirm `newapi-prod` reports `zqf_network`**
- [ ] **Step 5: Update production inventory docs only with verified outcomes**
