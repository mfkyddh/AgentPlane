# Production Linux Root SSH Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Switch repository-managed production Linux remote access from sudo-over-ubuntu to root-direct SSH, starting with `prod0-main`, while keeping local WSL behavior unchanged.

**Architecture:** Introduce a shared SSH target abstraction that can describe a remote Linux production host as `root_direct=true`, then route command rendering and execution through that abstraction instead of scattering `sudo` into each command string. Update the production host metadata and SSH config to make `prod0-main` use `root`, and enable the corresponding key-based root login on the host before switching callers.

**Tech Stack:** Python, OpenSSH client/server, unittest

---

### Task 1: Capture root-direct target rules in code

**Files:**
- Create: `ops/cli/ssh_targets.py`
- Modify: `ops/cli/apps.py`
- Modify: `ops/scripts/onepanel/env_targets.py`
- Test: `tests/test_app_cli.py`
- Test: `tests/test_onepanel_project_lifecycle.py`

- [ ] **Step 1: Write failing tests for production Linux SSH rendering**
- [ ] **Step 2: Run the targeted tests and verify the old sudo-based rendering fails expectations**
- [ ] **Step 3: Add the shared SSH target abstraction and command builders**
- [ ] **Step 4: Update app/onepanel callers to use the shared builders**
- [ ] **Step 5: Re-run the targeted tests and verify they pass**

### Task 2: Switch prod0-main metadata to root-direct SSH

**Files:**
- Modify: `secrets/ssh/config`
- Modify: `inventory/servers/prod0-main/inventory.json`
- Test: `tests/test_inventory_generation.py`
- Test: `tests/test_cli_entrypoints.py`

- [ ] **Step 1: Write failing assertions for `prod0-main` SSH user metadata where needed**
- [ ] **Step 2: Update the repository SSH config and inventory metadata from `ubuntu` to `root`**
- [ ] **Step 3: Re-run the affected tests and verify they pass**

### Task 3: Enable root key login on prod0-main and verify

**Files:**
- Modify: remote host `prod0-main:/root/.ssh/authorized_keys`

- [ ] **Step 1: Read the current `ubuntu` authorized keys and root SSH directory state**
- [ ] **Step 2: Install the matching public key into `/root/.ssh/authorized_keys` with strict permissions**
- [ ] **Step 3: Verify `ssh -F /root/work/OP_Linux/secrets/ssh/config root@prod0-main 'whoami'` returns `root`**

### Task 4: Run final verification

**Files:**
- Test: `tests/test_app_cli.py`
- Test: `tests/test_onepanel_project_lifecycle.py`
- Test: `tests/test_cli_entrypoints.py`
- Test: `tests/test_inventory_generation.py`

- [ ] **Step 1: Run the full targeted unittest set**
- [ ] **Step 2: Run direct SSH smoke checks against `prod0-main` with the repository config**
- [ ] **Step 3: Review the diff to confirm all production Linux command text now assumes root-direct SSH for `prod0-main`**
