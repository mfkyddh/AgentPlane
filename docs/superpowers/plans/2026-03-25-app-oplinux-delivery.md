# app-oplinux-delivery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create a global `app-oplinux-delivery` skill that teaches application-layer agents how to hand off Docker/Compose applications to the OP_Linux control plane without inventing a second production control plane.

**Architecture:** Keep OP_Linux docs and `ops.cli app` as execution truth, then add one global skill under the user skill directory that points agents at those truths, enforces trigger and non-trigger boundaries, and validates behavior with positive and negative prompt scenarios. Add only the minimum code/doc alignment needed so the skill does not lie about current `ops.cli` capabilities, especially around `schema_version`, repo discovery, and plan-only deploy/rollback behavior.

**Tech Stack:** Global Codex skills under `C:\Users\Administrator\.codex\skills`, Python stdlib tests in `tests/`, existing `ops.cli app` Python modules, Markdown specs/plans/docs

---

### Task 1: Map Files And Validation Surface

**Files:**
- Create: `docs/superpowers/plans/2026-03-25-app-oplinux-delivery.md`
- Reference: `docs/superpowers/specs/2026-03-25-app-oplinux-delivery-skill-design.md`
- Reference: `docs/architecture/op-linux-app-collaboration.md`
- Reference: `docs/architecture/op-linux-app-collaboration.md`
- Reference: `docs/runbooks/app-project-delivery-workflow.md`
- Reference: `ops/cli/apps.py`

- [ ] **Step 1: Re-read the approved spec and extract the exact v1 boundaries**
- [ ] **Step 2: Enumerate which current OP_Linux files are execution truth versus skill-only guidance**
- [ ] **Step 3: Lock the validation surface to one positive `sub2api` sample, one synthetic Docker/Compose sample, one infrastructure-only negative sample, and one non-onboarded-project negative sample**

### Task 2: Write Failing Skill Validation Scenarios First

**Files:**
- Create: `docs/superpowers/tmp/app-oplinux-delivery-baseline.md`
- Create: `docs/superpowers/tmp/app-oplinux-delivery-validation-prompts.md`

- [ ] **Step 1: Write a baseline note describing the current failure mode without the new skill**
- [ ] **Step 2: Write one prompt where an agent should route an application deployment task through OP_Linux and explicitly mention inventory/doc sync**
- [ ] **Step 3: Write one prompt where an agent should reject keeping production secrets or deploy scripts inside the application repo**
- [ ] **Step 4: Write one prompt where an agent should refuse to treat a pure 1Panel/OpenResty task as an application-delivery task**
- [ ] **Step 5: Write one prompt where an agent sees a sibling app repo without `deploy/op/contract.yaml` and should enter onboarding guidance instead of pretending deployment is possible**
- [ ] **Step 6: Write one prompt where there is no sibling `OP_Linux` repo and the agent should explicitly say the workflow is not yet applicable**
- [ ] **Step 7: Run a baseline subagent pass without the new skill and record the behavior in `docs/superpowers/tmp/app-oplinux-delivery-baseline.md`**

### Task 3: Align OP_Linux Execution Truth With The Planned Skill

**Files:**
- Modify: `ops/cli/apps.py`
- Modify: `tests/test_app_cli.py`
- Modify: `docs/architecture/op-linux-app-collaboration.md`
- Modify: `docs/runbooks/app-project-delivery-workflow.md`
- Modify: `<app_repo_root>/deploy/op/contract.yaml`

- [ ] **Step 1: Add `schema_version` handling to `ops/cli app` contract validation with backward-compatible legacy behavior**
- [ ] **Step 2: Add or update unit tests that cover `schema_version: 1` acceptance, legacy-contract compatibility, and explicit rejection of unsupported schema versions**
- [ ] **Step 3: Update `docs/architecture/op-linux-app-collaboration.md` so the formal contract example and workflow text match `schema_version: 1` and plan-first deploy/rollback behavior**
- [ ] **Step 4: Update `docs/runbooks/app-project-delivery-workflow.md` so it clearly matches the skill boundary: Docker/Compose v1 only, deploy/rollback plan-first**
- [ ] **Step 5: Add `schema_version: 1` to the real sample contract at `<app_repo_root>/deploy/op/contract.yaml` so the first formal sample uses the new contract shape**
- [ ] **Step 6: Run `uv run pytest -q tests/test_app_cli.py` and confirm the contract-alignment tests pass**
- [ ] **Step 7: Run `uv run python -m ops.cli app validate-contract --contract <app_repo_root>/deploy/op/contract.yaml --repo-root /root/work/OP_Linux/.worktrees/codex-op-linux-collab --target prod0-main` and confirm the real sample contract validates**
- [ ] **Step 8: Run `uv run python -m ops.cli app render-runtime --contract <app_repo_root>/deploy/op/contract.yaml --repo-root /root/work/OP_Linux/.worktrees/codex-op-linux-collab --target prod0-main --image-ref sub2api-prod:test` and confirm the real sample still renders**

### Task 4: Create The Global Skill Skeleton

**Files:**
- Create: `C:\Users\Administrator\.codex\skills\app-oplinux-delivery\SKILL.md`
- Create: `C:\Users\Administrator\.codex\skills\app-oplinux-delivery\references\trigger-rules.md`
- Create: `C:\Users\Administrator\.codex\skills\app-oplinux-delivery\references\source-of-truth-map.md`
- Create: `C:\Users\Administrator\.codex\skills\app-oplinux-delivery\references\execution-boundaries.md`
- Create: `C:\Users\Administrator\.codex\skills\app-oplinux-delivery\references\repo-discovery.md`
- Create: `C:\Users\Administrator\.codex\skills\app-oplinux-delivery\references\sub2api-example.md`

- [ ] **Step 1: Initialize the global skill directory with a valid `SKILL.md`**
- [ ] **Step 2: Write frontmatter so the description only expresses when to use the skill and when not to use it**
- [ ] **Step 3: Write the skill overview, hard rules, supported scope, unsupported scope, and the main Docker/Compose handoff workflow**
- [ ] **Step 4: Write the references files so they point to OP_Linux truth instead of duplicating full runbooks**
- [ ] **Step 5: Use `sub2api` as the only concrete worked example in the first version**
- [ ] **Step 6: Add `agents/openai.yaml` only if the skill packaging toolchain or local discovery check requires it**

### Task 5: Add Exact Skill Guidance For Application Agents

**Files:**
- Modify: `C:\Users\Administrator\.codex\skills\app-oplinux-delivery\SKILL.md`
- Modify: `C:\Users\Administrator\.codex\skills\app-oplinux-delivery\references\trigger-rules.md`
- Modify: `C:\Users\Administrator\.codex\skills\app-oplinux-delivery\references\execution-boundaries.md`
- Modify: `C:\Users\Administrator\.codex\skills\app-oplinux-delivery\references\repo-discovery.md`

- [ ] **Step 1: Add the minimum activation signals required before the skill should take over**
- [ ] **Step 2: Add explicit non-trigger cases for infrastructure-only, 1Panel-only, OpenResty-only, and non-app-host-governance tasks**
- [ ] **Step 3: Add a repo-discovery decision path for sibling OP_Linux detection, explicit `--repo-root`, and missing-contract onboarding**
- [ ] **Step 4: Add an execution-boundary section that states `deploy` and `rollback` are plan-only in the current OP_Linux CLI unless the user explicitly approves a real cutover**
- [ ] **Step 5: Add common-mistakes guidance so future agents do not duplicate secrets, create parallel deploy scripts, or manage websites as if they were application truth**

### Task 6: Validate The Skill With Positive And Negative Scenarios

**Files:**
- Modify: `docs/superpowers/tmp/app-oplinux-delivery-baseline.md`
- Modify: `docs/superpowers/tmp/app-oplinux-delivery-validation-prompts.md`
- Reference: `C:\Users\Administrator\.codex\skills\app-oplinux-delivery\SKILL.md`

- [ ] **Step 1: Run a positive subagent validation on a `sub2api`-style deployment request using the new skill and assert the answer routes through OP_Linux CLI plus inventory/doc sync**
- [ ] **Step 2: Run a positive subagent validation on a synthetic Docker/Compose app onboarding request that is not `sub2api`**
- [ ] **Step 3: Run a negative subagent validation on a prompt that tries to keep production secrets or deploy scripts in the app repo and verify the skill rejects that model**
- [ ] **Step 4: Run a negative subagent validation on a pure 1Panel/OpenResty task and verify the skill does not hijack it**
- [ ] **Step 5: Run a negative subagent validation on a project with no `deploy/op/contract.yaml` and verify the agent switches to onboarding guidance**
- [ ] **Step 6: Run a negative subagent validation on a project with no sibling `OP_Linux` repo and verify the agent marks the workflow as not yet applicable**
- [ ] **Step 7: Capture failures or rationalizations, tighten the skill, and re-run until the validation set is stable**

### Task 7: Validate Skill Packaging And Local Discovery

**Files:**
- Modify: `C:\Users\Administrator\.codex\skills\app-oplinux-delivery\SKILL.md`

- [ ] **Step 1: Run `python C:\Users\Administrator\.codex\skills\.system\skill-creator\scripts\quick_validate.py C:\Users\Administrator\.codex\skills\app-oplinux-delivery`**
- [ ] **Step 2: If `agents/openai.yaml` exists, run `python C:\Users\Administrator\.codex\skills\.system\skill-creator\scripts\generate_openai_yaml.py C:\Users\Administrator\.codex\skills\app-oplinux-delivery` or the equivalent check required by that packaging flow**
- [ ] **Step 3: Confirm the skill folder name, frontmatter, and description satisfy global skill naming and trigger requirements**
- [ ] **Step 4: Spot-check that the skill can be found from the global skill root and that the references are reachable**

### Task 8: Final Verification And Commits

**Files:**
- Modify: `ops/cli/apps.py`
- Modify: `tests/test_app_cli.py`
- Modify: `docs/architecture/op-linux-app-collaboration.md`
- Modify: `docs/runbooks/app-project-delivery-workflow.md`
- Modify: `<app_repo_root>/deploy/op/contract.yaml`
- Create: `C:\Users\Administrator\.codex\skills\app-oplinux-delivery\*`

- [ ] **Step 1: Run `uv run pytest -q` in `/root/work/OP_Linux/.worktrees/codex-op-linux-collab`**
- [ ] **Step 2: Re-run the validated positive and negative skill scenarios and record the final results**
- [ ] **Step 3: Commit the OP_Linux code/doc alignment changes**
- [ ] **Step 4: Commit the global skill files under `C:\Users\Administrator\.codex\skills\app-oplinux-delivery` if that skill repository is versioned; otherwise capture the exact installed file set in the final report**
- [ ] **Step 5: Summarize residual risks, especially that v1 is Docker/Compose-only and that real cutover still requires explicit user approval**
