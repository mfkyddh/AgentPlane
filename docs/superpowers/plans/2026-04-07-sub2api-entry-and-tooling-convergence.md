# Sub2API Entry And Tooling Convergence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Repair `/root/work/sub2api` so its active entry files, Codex environment, and repo-local skills all point at the current OP_Linux CLI-first control plane.

**Architecture:** Keep all implementation work inside `/root/work/sub2api` and do not change live runtime or deployment truth. First fix the human-facing entry files (`AGENTS.md`, `README.md`, `Makefile`) so they stop sending people to dead paths or the retired `/root/work/env_ubuntu` control plane. Then convert `.codex/environments/` into a script-backed WSL-first structure and rewrite repo-local skills so they become thin bridges into `/root/work/OP_Linux` runbooks and `app delivery` commands.

**Tech Stack:** Markdown, Makefile, TOML, Bash, PowerShell, Git worktrees, `rg`, `pwsh`, `python3` (`tomllib`)

---

## File Map

- `/root/work/sub2api/AGENTS.md`
  Repository entrypoint. Must become the 6-section repo contract and stop referencing missing `.planning/*` files.
- `/root/work/sub2api/README.md`
  Public README. Needs one minimal maintainer/operator docs section that points to live owner-facing material without pulling Phase 3 doc migration forward.
- `/root/work/sub2api/Makefile`
  Human command surface. Must stop advertising dead targets and retired `/root/work/env_ubuntu` commands.
- `/root/work/sub2api/.gitignore`
  Must allow repo-owned `.codex/environments/**` files to be tracked while still ignoring unrelated local Codex state.
- `/root/work/sub2api/.codex/environments/environment.toml`
  Thin Codex entrypoint. Must move from Win32-only inline commands to repo-owned script files.
- `/root/work/sub2api/.codex/environments/setup/*`
  Setup scripts. Must provide WSL-first setup plus a Windows bridge entry that only forwards into WSL.
- `/root/work/sub2api/.codex/environments/actions/*`
  Common manual actions. Must wrap the existing `tools/wsl/sub2api-dev` interface instead of embedding long commands in TOML.
- `/root/work/sub2api/.codex/environments/lib/common.sh`
  Shared shell helpers for `.codex/environments`.
- `/root/work/sub2api/.agents/skills/README.md`
  New repo-local skill index. Must explain which repo-local skill handles local work and which OP_Linux skill owns formal app delivery.
- `/root/work/sub2api/.agents/skills/sub2api-prod-deploy/SKILL.md`
  Repo-local production bridge. Must stop using `app ... --contract`, stop referencing `docs/OP_LINUX_DEPLOYMENT.md`, and route to `app-delivery-ops`.
- `/root/work/sub2api/.agents/skills/sub2api-source-build/SKILL.md`
  Local source-build skill. Must stop teaching the legacy `app build-artifact --contract` CLI shape.
- `/root/work/sub2api/.agents/skills/sub2api-wsl-dev/SKILL.md`
  Daily dev skill. Must keep WSL-first semantics and update the Windows bridge example from `powershell.exe` to `pwsh`.
- `/root/work/sub2api/tools/windows/sub2api-codex-wsl.ps1`
  Windows bridge helper. Its own help text must stop teaching `powershell.exe`.

### Task 1: Repair Repo Entry Files

**Files:**
- Modify: `/root/work/sub2api/AGENTS.md`
- Modify: `/root/work/sub2api/README.md`
- Modify: `/root/work/sub2api/Makefile`
- Test: repository invariant scan over `/root/work/sub2api/AGENTS.md`, `/root/work/sub2api/README.md`, `/root/work/sub2api/Makefile`

- [ ] **Step 1: Create an isolated worktree and capture the current failing entry-point invariants**

```bash
cd /root/work/sub2api
make worktree-init BRANCH=codex/sub2api-entry-tooling BASE=main CLEANUP_ON_FAIL=1
cd /root/work/sub2api/.worktrees/codex/sub2api-entry-tooling
rg -n '\.planning/PROJECT|\.planning/ROADMAP|/root/work/env_ubuntu|datamanagement|secret_scan\.py' AGENTS.md README.md Makefile
```

Expected: `rg` prints matches from `AGENTS.md` and `Makefile`, proving the current entry surface still advertises dead paths and dead targets.

- [ ] **Step 2: Rewrite `AGENTS.md` into the 6-section repo contract**

```markdown
# Repository Working Rules

## Scope

- These rules apply to `/root/work/sub2api`.
- Default to Chinese when replying to the repository owner unless explicitly requested otherwise.
- Keep this file short and durable; put long-form maintenance details in repo docs.

## Repo Map

- `README.md`: public project entry and high-level deployment overview.
- `DEV_GUIDE.md`: local development pitfalls and corrective notes.
- `docs/OP_LINUX_DEPLOYMENT.wsl.md`: non-sensitive WSL summary written by OP_Linux.
- `docs/OP_LINUX_DEPLOYMENT.prod0-main.md`: non-sensitive prod0 summary written by OP_Linux.
- `docs/OP_LINUX_DEPLOYMENT.prod2-main.md`: non-sensitive prod2 summary written by OP_Linux.
- `zqfdocs/README.md`: legacy owner notes pending Phase 3 migration; do not treat as the formal control plane.
- `deploy/op/`: app-delivery contracts consumed by OP_Linux.
- `tools/wsl/sub2api-dev`: standard WSL daily workflow wrapper.
- `.agents/skills/`: repo-local skills for local development and repo context.
- `.codex/environments/`: Codex environment entrypoints for this repo.

## Standard Commands

- Daily local workflow: `make wsl-preflight`, `make wsl-build`, `make wsl-bootstrap`, `make wsl-run`, `make wsl-stop`, `make wsl-status`
- Split dev workflow: `make wsl-dev-up`, `make wsl-dev-down`, `make wsl-debug-backend`, `make wsl-logs target=<runtime|backend|frontend|dlv>`
- Tests: `make test-backend`, `make test-frontend`
- Runtime image packaging input: `make build-runtime-artifacts`, `make package-runtime-image IMAGE_TAG=local`
- Git hooks: `make git-hooks-install`
- Worktree creation: `make worktree-init BRANCH=codex/<topic> BASE=main CLEANUP_ON_FAIL=1`
- Formal onboarding/deploy/rollback/verify/doc-sync: run `uv run python -m ops.cli app object ...` or `uv run python -m ops.cli app delivery ...` from `/root/work/OP_Linux`

## Working Rules

- Default to WSL-first for build, test, git, and local runtime operations.
- This repository does not own the formal production control plane; do not add a second deploy/rollback/website workflow here.
- Keep real secrets in untracked local files; do not commit `.env`, `.prod-jump.env`, or other secret-bearing files.
- Repo-local skills may guide local work, but formal app delivery must route to `/root/work/OP_Linux`.
- Use a non-`main` branch or worktree for any repo changes.

## Definition Of Done

- Run the smallest relevant verification after each change.
- For docs and command-surface changes, verify with `rg`, syntax parsers, and wrapper help output instead of assuming text is correct.
- If something cannot be verified, state exactly what was not verified and why.

## Docs

- Public project overview: `README.md`
- Local dev guide: `DEV_GUIDE.md`
- Current non-sensitive OP_Linux summaries: `docs/OP_LINUX_DEPLOYMENT.*.md`
- Legacy owner notes pending migration: `zqfdocs/README.md`
```

- [ ] **Step 3: Add a minimal maintainer/operator navigation block to `README.md`**

```markdown
## Maintainer Notes

The formal production control plane for this fork lives in `/root/work/OP_Linux`.

- Local development guide: `DEV_GUIDE.md`
- Non-sensitive OP_Linux summaries:
  - `docs/OP_LINUX_DEPLOYMENT.wsl.md`
  - `docs/OP_LINUX_DEPLOYMENT.prod0-main.md`
  - `docs/OP_LINUX_DEPLOYMENT.prod2-main.md`
- Legacy owner notes pending migration: `zqfdocs/README.md`

Use this repository to prepare code, tests, contracts, and build assets. Run formal onboarding, deploy, verify, rollback, inventory refresh, and doc-sync from `/root/work/OP_Linux`.
```

- [ ] **Step 4: Remove dead Makefile targets and rewrite the `prod-*` wrappers to the OP_Linux `app delivery` surface**

```makefile
.PHONY: build build-backend build-frontend build-runtime-artifacts package-runtime-image test test-backend test-backend-security test-frontend \
	wsl-help wsl-preflight wsl-build wsl-bootstrap wsl-run wsl-stop wsl-status wsl-dev-up wsl-dev-down wsl-debug-backend wsl-logs git-hooks-install \
	worktree-init \
	prod-package prod-deploy prod-rollback prod-verify prod-verify-origin prod-verify-public prod-verify-ws-origin prod-verify-ws-public

# Archived helper: formal release packaging now goes through OP_Linux app delivery build-artifact.
prod-package:
	@VERSION="$(VERSION)" bash deploy/prod/package-release.sh

prod-deploy:
	@echo "Formal production deploy moved to /root/work/OP_Linux. Use: uv run python -m ops.cli app delivery deploy --target prod0-main --app sub2api --repo-root /root/work/OP_Linux --dry-run" >&2
	@exit 1

prod-rollback:
	@echo "Formal production rollback moved to /root/work/OP_Linux. Use: uv run python -m ops.cli app delivery rollback --target prod0-main --app sub2api --repo-root /root/work/OP_Linux --dry-run" >&2
	@exit 1

prod-verify-origin:
	@echo "Formal production verification moved to /root/work/OP_Linux. Use: uv run python -m ops.cli app delivery verify --target prod0-main --app sub2api --repo-root /root/work/OP_Linux --execute" >&2
	@exit 1

prod-verify-public:
	@echo "Formal public-entry verification moved to /root/work/OP_Linux app delivery verify plus the OP_Linux website runbooks." >&2
	@exit 1

prod-verify:
	@echo "Formal production verification moved to /root/work/OP_Linux. Run app delivery verify there, then refresh inventory and doc-sync." >&2
	@exit 1

prod-verify-ws-origin:
	@echo "WebSocket verification is now part of /root/work/OP_Linux formal verify and website checks." >&2
	@exit 1

prod-verify-ws-public:
	@echo "WebSocket verification is now part of /root/work/OP_Linux formal verify and website checks." >&2
	@exit 1
```

- [ ] **Step 5: Re-run the entry-point invariant scan and verify the repo no longer advertises dead paths**

Run:

```bash
cd /root/work/sub2api/.worktrees/codex/sub2api-entry-tooling
rg -n '\.planning/PROJECT|\.planning/ROADMAP|/root/work/env_ubuntu|datamanagement|secret_scan\.py' AGENTS.md README.md Makefile
git diff --check
```

Expected: `rg` prints nothing; `git diff --check` prints nothing.

- [ ] **Step 6: Commit the entry-point repair as one focused change**

```bash
cd /root/work/sub2api/.worktrees/codex/sub2api-entry-tooling
git add AGENTS.md README.md Makefile
git commit -m "docs: align repo entry and command surface"
```

### Task 2: Standardize `.codex/environments`

**Files:**
- Modify: `/root/work/sub2api/.gitignore`
- Modify: `/root/work/sub2api/.codex/environments/environment.toml`
- Create: `/root/work/sub2api/.codex/environments/lib/common.sh`
- Create: `/root/work/sub2api/.codex/environments/setup/setup.sh`
- Create: `/root/work/sub2api/.codex/environments/setup/setup.linux.sh`
- Create: `/root/work/sub2api/.codex/environments/setup/setup.windows.ps1`
- Create: `/root/work/sub2api/.codex/environments/actions/preflight.sh`
- Create: `/root/work/sub2api/.codex/environments/actions/bootstrap.sh`
- Create: `/root/work/sub2api/.codex/environments/actions/build.sh`
- Create: `/root/work/sub2api/.codex/environments/actions/run.sh`
- Create: `/root/work/sub2api/.codex/environments/actions/stop.sh`
- Create: `/root/work/sub2api/.codex/environments/actions/status.sh`
- Create: `/root/work/sub2api/.codex/environments/actions/logs.sh`
- Create: `/root/work/sub2api/.codex/environments/actions/dev-up.sh`
- Create: `/root/work/sub2api/.codex/environments/actions/debug-backend.sh`
- Test: syntax and parse checks over `/root/work/sub2api/.codex/environments/**`

- [ ] **Step 1: Prove the current repo-owned environment layout is incomplete**

Run:

```bash
cd /root/work/sub2api/.worktrees/codex/sub2api-entry-tooling
test -d .codex/environments/setup || echo "missing setup/"
test -d .codex/environments/actions || echo "missing actions/"
test -d .codex/environments/lib || echo "missing lib/"
git check-ignore -v .codex/environments/environment.toml
```

Expected: the first three checks print `missing ...`; `git check-ignore -v` reports the blanket `.codex/` ignore rule.

- [ ] **Step 2: Update `.gitignore` so repo-owned Codex environment files can be tracked**

```gitignore
.codex/*
!.codex/environments/
!.codex/environments/**
```

Replace the old blanket `.codex/` ignore line with the three-line block above. Keep unrelated local Codex state ignored.

- [ ] **Step 3: Replace `environment.toml` and add shared setup helpers**

```toml
# /root/work/sub2api/.codex/environments/environment.toml
[setup]
default = "bash .codex/environments/setup/setup.sh"
linux = "bash .codex/environments/setup/setup.linux.sh"
windows = "pwsh -File .codex/environments/setup/setup.windows.ps1"

[[actions]]
name = "Preflight"
command = ".codex/environments/actions/preflight.sh"

[[actions]]
name = "Bootstrap"
command = ".codex/environments/actions/bootstrap.sh"

[[actions]]
name = "Build"
command = ".codex/environments/actions/build.sh"

[[actions]]
name = "Run"
command = ".codex/environments/actions/run.sh"

[[actions]]
name = "Stop"
command = ".codex/environments/actions/stop.sh"

[[actions]]
name = "Status"
command = ".codex/environments/actions/status.sh"

[[actions]]
name = "Logs"
command = ".codex/environments/actions/logs.sh"

[[actions]]
name = "Dev Up"
command = ".codex/environments/actions/dev-up.sh"

[[actions]]
name = "Debug Backend"
command = ".codex/environments/actions/debug-backend.sh"
```

```bash
# /root/work/sub2api/.codex/environments/lib/common.sh
#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"

cd_repo_root() {
  cd "${REPO_ROOT}"
}

resolve_primary_worktree_root() {
  git -C "${REPO_ROOT}" worktree list --porcelain | awk '$1=="worktree"{print substr($0,10); exit}'
}

ensure_local_env_file() {
  cd_repo_root
  if [[ -f .env ]]; then
    return 0
  fi

  local primary_root primary_env
  primary_root="$(resolve_primary_worktree_root)"
  primary_env="${primary_root}/.env"

  if [[ -n "${primary_root}" && -f "${primary_env}" && "$(pwd -P)" != "${primary_root}" ]]; then
    ln -s "${primary_env}" .env
    printf 'linked .env -> %s\n' "${primary_env}"
  fi
}

run_dev() {
  cd_repo_root
  tools/wsl/sub2api-dev "$@"
}

run_make() {
  cd_repo_root
  make "$@"
}
```

```bash
# /root/work/sub2api/.codex/environments/setup/setup.sh
#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
bash "${script_dir}/setup.linux.sh"
```

```bash
# /root/work/sub2api/.codex/environments/setup/setup.linux.sh
#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
. "${script_dir}/../lib/common.sh"

ensure_local_env_file
cd_repo_root

pnpm --dir frontend install --frozen-lockfile
(
  cd backend
  go mod download
)

run_make git-hooks-install

if [[ -f "${REPO_ROOT}/.env" ]]; then
  run_dev preflight
else
  printf 'skip preflight: .env not found in %s\n' "${REPO_ROOT}"
fi
```

```powershell
# /root/work/sub2api/.codex/environments/setup/setup.windows.ps1
[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoDirWindows = (Get-Location).ProviderPath
$repoDirWsl = (& wsl.exe -e wslpath -a $repoDirWindows | Out-String).Trim()
if ([string]::IsNullOrWhiteSpace($repoDirWsl)) {
  throw "Unable to resolve the current workspace path to a WSL path: $repoDirWindows"
}

$bridgePath = Join-Path $PSScriptRoot "..\..\..\tools\windows\sub2api-codex-wsl.ps1"
$linuxScript = Join-Path $PSScriptRoot "setup.linux.sh"

if (-not (Test-Path -LiteralPath $bridgePath)) {
  throw "Bridge script not found: $bridgePath"
}
if (-not (Test-Path -LiteralPath $linuxScript)) {
  throw "Linux setup script not found: $linuxScript"
}

& $bridgePath -RepoDir $repoDirWsl -File $linuxScript
exit $LASTEXITCODE
```

- [ ] **Step 4: Add thin action scripts that wrap the existing `tools/wsl/sub2api-dev` surface**

```bash
# /root/work/sub2api/.codex/environments/actions/preflight.sh
#!/usr/bin/env bash
set -euo pipefail
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "${script_dir}/../lib/common.sh"
ensure_local_env_file
run_dev preflight

# /root/work/sub2api/.codex/environments/actions/bootstrap.sh
#!/usr/bin/env bash
set -euo pipefail
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "${script_dir}/../lib/common.sh"
ensure_local_env_file
run_dev bootstrap

# /root/work/sub2api/.codex/environments/actions/build.sh
#!/usr/bin/env bash
set -euo pipefail
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "${script_dir}/../lib/common.sh"
ensure_local_env_file
run_dev build

# /root/work/sub2api/.codex/environments/actions/run.sh
#!/usr/bin/env bash
set -euo pipefail
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "${script_dir}/../lib/common.sh"
ensure_local_env_file
run_dev run

# /root/work/sub2api/.codex/environments/actions/stop.sh
#!/usr/bin/env bash
set -euo pipefail
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "${script_dir}/../lib/common.sh"
run_dev stop

# /root/work/sub2api/.codex/environments/actions/status.sh
#!/usr/bin/env bash
set -euo pipefail
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "${script_dir}/../lib/common.sh"
ensure_local_env_file
run_dev status

# /root/work/sub2api/.codex/environments/actions/logs.sh
#!/usr/bin/env bash
set -euo pipefail
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "${script_dir}/../lib/common.sh"
run_dev logs runtime

# /root/work/sub2api/.codex/environments/actions/dev-up.sh
#!/usr/bin/env bash
set -euo pipefail
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "${script_dir}/../lib/common.sh"
ensure_local_env_file
run_dev dev-up

# /root/work/sub2api/.codex/environments/actions/debug-backend.sh
#!/usr/bin/env bash
set -euo pipefail
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "${script_dir}/../lib/common.sh"
ensure_local_env_file
run_dev debug-backend
```

- [ ] **Step 5: Validate the environment contract with syntax and parser checks**

Run:

```bash
cd /root/work/sub2api/.worktrees/codex/sub2api-entry-tooling
python3 - <<'PY'
from pathlib import Path
import tomllib
with open('.codex/environments/environment.toml', 'rb') as fh:
    tomllib.load(fh)
required = [
    Path('.codex/environments/lib/common.sh'),
    Path('.codex/environments/setup/setup.sh'),
    Path('.codex/environments/setup/setup.linux.sh'),
    Path('.codex/environments/setup/setup.windows.ps1'),
]
missing = [str(path) for path in required if not path.exists()]
if missing:
    raise SystemExit(f"missing expected environment files: {missing}")
print("environment.toml and required files: ok")
PY

bash -n .codex/environments/lib/common.sh .codex/environments/setup/*.sh .codex/environments/actions/*.sh
pwsh -NoProfile -Command '$tokens=$null; $errors=$null; [System.Management.Automation.Language.Parser]::ParseFile((Resolve-Path ".codex/environments/setup/setup.windows.ps1"), [ref]$tokens, [ref]$errors) | Out-Null; if ($errors.Count -gt 0) { $errors; exit 1 }'
if git check-ignore -q .codex/environments/setup/setup.linux.sh; then echo ".codex environment files are still ignored" >&2; exit 1; fi
```

Expected: parser checks exit `0`; the final `git check-ignore` guard does not print an error.

- [ ] **Step 6: Commit the environment refactor separately**

```bash
cd /root/work/sub2api/.worktrees/codex/sub2api-entry-tooling
git add .gitignore .codex/environments
git commit -m "chore: standardize codex environment entrypoints"
```

### Task 3: Converge Repo-Local Skills To OP_Linux

**Files:**
- Create: `/root/work/sub2api/.agents/skills/README.md`
- Modify: `/root/work/sub2api/.agents/skills/sub2api-prod-deploy/SKILL.md`
- Modify: `/root/work/sub2api/.agents/skills/sub2api-source-build/SKILL.md`
- Modify: `/root/work/sub2api/.agents/skills/sub2api-wsl-dev/SKILL.md`
- Modify: `/root/work/sub2api/tools/windows/sub2api-codex-wsl.ps1`
- Test: stale-guidance scan over `/root/work/sub2api/.agents/skills/**` and `/root/work/sub2api/tools/windows/sub2api-codex-wsl.ps1`

- [ ] **Step 1: Capture the current stale skill references before editing**

Run:

```bash
cd /root/work/sub2api/.worktrees/codex/sub2api-entry-tooling
rg -n 'docs/OP_LINUX_DEPLOYMENT\.md|uv run python -m ops\.cli app .*--contract|powershell\.exe' .agents/skills tools/windows/sub2api-codex-wsl.ps1
```

Expected: hits appear in `sub2api-prod-deploy/SKILL.md`, `sub2api-source-build/SKILL.md`, `sub2api-wsl-dev/SKILL.md`, and `tools/windows/sub2api-codex-wsl.ps1`.

- [ ] **Step 2: Add a repo-local skill index that makes the OP_Linux boundary explicit**

```markdown
# Sub2API repo-level skills

Use repo-local skills for local development, source builds, bootstrap, and local reset work in `/root/work/sub2api`.

- `sub2api-wsl-dev`: daily WSL run/debug/status/log workflows
- `sub2api-source-build`: source build before bootstrap or runtime repair
- `sub2api-wsl-bootstrap`: env-first bootstrap after a successful source build
- `sub2api-wsl-runtime-reset`: destructive local reset before rebuild
- `sub2api-prod-deploy`: thin bridge into the OP_Linux formal app-delivery control plane

Formal app delivery source of truth:

- `/root/work/OP_Linux/.codex/skills/app-delivery-ops/SKILL.md`
- `/root/work/OP_Linux/docs/runbooks/app-project-delivery-workflow.md`

Do not create a second production deploy or rollback workflow in this repository.
```

- [ ] **Step 3: Rewrite `sub2api-prod-deploy/SKILL.md` as a thin bridge to `app-delivery-ops`**

```markdown
---
name: sub2api-prod-deploy
description: Use when /root/work/sub2api needs to hand a release candidate to the OP_Linux control plane for formal delivery, verification, rollback, or WSL rehearsal.
---

# Sub2API Production Delivery Bridge

This repo-local skill is only a bridge. Formal deploy, rollback, verify, inventory refresh, and doc-sync actions run from `/root/work/OP_Linux`.

## Source Of Truth

- `/root/work/sub2api/AGENTS.md`
- `/root/work/sub2api/deploy/op/contract.yaml`
- `/root/work/OP_Linux/.codex/skills/app-delivery-ops/SKILL.md`
- `/root/work/OP_Linux/docs/runbooks/app-project-delivery-workflow.md`
- `/root/work/OP_Linux/docs/architecture/op-linux-app-collaboration.md`

## Formal Command Surface

- `uv run python -m ops.cli app object get --target prod0-main --app sub2api --repo-root /root/work/OP_Linux`
- `uv run python -m ops.cli app delivery validate-contract --target prod0-main --app sub2api --repo-root /root/work/OP_Linux`
- `uv run python -m ops.cli app delivery build-artifact --target prod0-main --app sub2api --repo-root /root/work/OP_Linux --auto-version`
- `uv run python -m ops.cli app delivery ship-image --target prod0-main --app sub2api --repo-root /root/work/OP_Linux --image-ref sub2api-prod:<tag>`
- `uv run python -m ops.cli app delivery deploy --target prod0-main --app sub2api --repo-root /root/work/OP_Linux --dry-run`
- `uv run python -m ops.cli app delivery deploy --target prod0-main --app sub2api --repo-root /root/work/OP_Linux --execute`
- `uv run python -m ops.cli app delivery verify --target prod0-main --app sub2api --repo-root /root/work/OP_Linux --execute`
- `uv run python -m ops.cli app delivery rollback --target prod0-main --app sub2api --repo-root /root/work/OP_Linux --dry-run`
- `uv run python -m ops.cli app delivery inventory-refresh --target prod0-main --app sub2api --repo-root /root/work/OP_Linux --write`
- `uv run python -m ops.cli app delivery doc-sync --target prod0-main --app sub2api --repo-root /root/work/OP_Linux --write`

For local WSL rehearsal after the target is formally onboarded:

- `uv run python -m ops.cli app delivery validate-contract --target wsl --app sub2api --repo-root /root/work/OP_Linux`
- `uv run python -m ops.cli app delivery build-artifact --target wsl --app sub2api --repo-root /root/work/OP_Linux --auto-version`
- `uv run python -m ops.cli app delivery deploy --target wsl --app sub2api --repo-root /root/work/OP_Linux --execute`
- `uv run python -m ops.cli app delivery verify --target wsl --app sub2api --repo-root /root/work/OP_Linux --execute`

## Guardrails

- Do not use `make prod-*` as a formal deployment path.
- Do not reintroduce `app ... --contract` examples in this repository.
- Do not reference `/root/work/sub2api/docs/OP_LINUX_DEPLOYMENT.md`; the live summary files are target-aware.
- Treat this skill as repo-local guidance only. The formal execution truth stays in `/root/work/OP_Linux`.
```

- [ ] **Step 4: Align the remaining local skills and the Windows bridge help text**

```markdown
# /root/work/sub2api/.agents/skills/sub2api-source-build/SKILL.md
Replace the stale production handoff bullet:

- `uv run python -m ops.cli app delivery build-artifact --target prod0-main --app sub2api --repo-root /root/work/OP_Linux --auto-version`

# /root/work/sub2api/.agents/skills/sub2api-wsl-dev/SKILL.md
Replace the Windows bridge bullet with:

- when operating from Codex Desktop / PowerShell with multiline POSIX shell, use `pwsh -File .\tools\windows\sub2api-codex-wsl.ps1` instead of pasting raw shell into PowerShell
```

```powershell
# /root/work/sub2api/tools/windows/sub2api-codex-wsl.ps1
$usage = @"
Usage:
  @'
  set -euo pipefail
  git status --short
  '@ | pwsh -File .\tools\windows\sub2api-codex-wsl.ps1

  pwsh -File .\tools\windows\sub2api-codex-wsl.ps1 -File .\tmp\script.sh

Purpose:
  Feed POSIX shell text to WSL bash over stdin so PowerShell does not pre-parse
  shell quotes, $, \, or command substitutions before bash receives them.
"@
```

- [ ] **Step 5: Verify the active repo-local guidance no longer contains the retired command shapes**

Run:

```bash
cd /root/work/sub2api/.worktrees/codex/sub2api-entry-tooling
rg -n 'docs/OP_LINUX_DEPLOYMENT\.md|powershell\.exe' .agents/skills tools/windows/sub2api-codex-wsl.ps1
rg -n 'uv run python -m ops\.cli app (validate-contract|build-artifact|ship-image|deploy|verify|rollback|inventory-refresh|doc-sync).*--contract' .agents/skills
rg -n 'uv run python -m ops\.cli app delivery .*--target .*--app sub2api' .agents/skills/sub2api-prod-deploy/SKILL.md .agents/skills/sub2api-source-build/SKILL.md
```

Expected:
- the first two `rg` commands print nothing
- the third `rg` command prints the new `app delivery --target ... --app sub2api` command lines

- [ ] **Step 6: Commit the skill convergence separately**

```bash
cd /root/work/sub2api/.worktrees/codex/sub2api-entry-tooling
git add .agents/skills tools/windows/sub2api-codex-wsl.ps1
git commit -m "docs: route repo skills to op_linux delivery"
```

## Self-Review

- Spec coverage:
  - Phase 1 entry cleanup is covered by Task 1.
  - Phase 2 Codex environment standardization is covered by Task 2.
  - Phase 2 repo skill convergence and global-skill retirement fallout are covered by Task 3.
  - Phase 3+ work (`docs/README.md`, `docs/owner/`, `docs/archive/`, `secrets/local/`, generated artifact cleanup, `contract.wsl.yaml`, prod2 website truth) is intentionally out of scope for this plan.
- Placeholder scan:
  - No unfinished placeholder markers remain.
  - Each code-changing step contains the concrete text to add or replace.
- Consistency:
  - All formal delivery commands use `uv run python -m ops.cli app delivery --target <target> --app sub2api --repo-root /root/work/OP_Linux`.
  - All repo-level Codex files live under `.codex/environments/{setup,actions,lib}` and are explicitly tracked via `.gitignore`.
