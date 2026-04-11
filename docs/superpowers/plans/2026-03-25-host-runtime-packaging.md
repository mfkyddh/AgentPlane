# Host Runtime Packaging Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 `sub2api` 的正式镜像构建主路径改成“WSL 宿主机预编译产物，再用 runtime Dockerfile 打包镜像”，并在 `OP_Linux` 中把这套模式固化为后续 Docker 类项目的标准推荐做法。

**Architecture:** 方案分两段执行。第一段在 `sub2api` 仓库的 WSL 宿主机直接完成前端构建、Go 编译和 runtime 资源收口，输出统一制品目录。第二段用一个只消费制品目录的 runtime Dockerfile 生成镜像，随后继续走 `OP_Linux` 现有的 `build-artifact -> ship-image -> render-runtime` 正式交付链路。

**Tech Stack:** Bash, Docker, Go, pnpm, Python (`uv` + `pytest`), OP_Linux `ops.cli`

---

### Task 1: Lock OP_Linux Expectations With Tests

**Files:**
- Modify: `/root/work/OP_Linux/.worktrees/codex-host-runtime-packaging/tests/test_app_cli.py`
- Modify: `/root/work/OP_Linux/.worktrees/codex-host-runtime-packaging/ops/cli/apps.py` (only if tests reveal command passthrough gaps)
- Test: `/root/work/OP_Linux/.worktrees/codex-host-runtime-packaging/tests/test_app_cli.py`

- [ ] **Step 1: Write the failing test for script-based artifact builds**

Add or update tests in `tests/test_app_cli.py` so they expect `artifact.build_command` to be a repo-local script entry such as `bash deploy/package-runtime-image.sh`, and ensure `build_artifact()` still injects `IMAGE_TAG` while preserving the script command.

- [ ] **Step 2: Run the focused test to verify it fails for the expected reason**

Run:

```bash
wsl.exe -u root -e bash -lc 'cd /root/work/OP_Linux/.worktrees/codex-host-runtime-packaging && uv run python -m pytest tests/test_app_cli.py -q -k build_artifact'
```

Expected:

- At least one new assertion fails because tests still expect raw `docker build` or because `build_artifact()` output does not yet match the new command form.
- Ignore the known unrelated `tenant_resources` baseline failures.

- [ ] **Step 3: Write the minimal implementation only if the new test exposes a real apps.py gap**

If the new test fails because `ops/cli/apps.py` mishandles script commands, update only the minimal path inside `build_artifact()`. If the command passthrough already works, skip production code changes and leave the task test-only.

- [ ] **Step 4: Re-run the focused test to verify it passes**

Run:

```bash
wsl.exe -u root -e bash -lc 'cd /root/work/OP_Linux/.worktrees/codex-host-runtime-packaging && uv run python -m pytest tests/test_app_cli.py -q -k build_artifact'
```

Expected:

- The new `build_artifact` expectation passes.
- No new failures appear beyond the known unrelated tenant tests.

- [ ] **Step 5: Commit the OP_Linux expectation lock**

```bash
wsl.exe -u root -e bash -lc 'cd /root/work/OP_Linux/.worktrees/codex-host-runtime-packaging && git add tests/test_app_cli.py ops/cli/apps.py && git commit -m "test: lock script-based artifact builds"'
```

### Task 2: Create an Isolated Sub2API Worktree and Verify the Baseline

**Files:**
- Create/Use: `/root/work/sub2api/.worktrees/codex/host-runtime-packaging` or the repository-preferred worktree path discovered at execution time
- Read: `/root/work/sub2api/deploy/op/contract.yaml`
- Read: `/root/work/sub2api/Dockerfile.goreleaser`
- Read: `/root/work/sub2api/Makefile`
- Read: `/root/work/sub2api/backend/Makefile`

- [ ] **Step 1: Set up a sub2api worktree using the worktree skill rules**

Verify the preferred worktree directory in `/root/work/sub2api`, ensure it is ignored, and create a branch such as `codex/host-runtime-packaging`.

- [ ] **Step 2: Run the relevant baseline checks**

Run the smallest useful pre-change checks that establish current behavior:

```bash
wsl.exe -u root -e bash -lc 'cd /root/work/sub2api/<worktree> && test -f backend/go.mod && go test ./backend/...'
wsl.exe -u root -e bash -lc 'cd /root/work/sub2api/<worktree> && test -f frontend/package.json && pnpm --dir frontend run typecheck'
```

Expected:

- Report any pre-existing failures before changing packaging assets.
- If checks are too heavy or flaky, narrow to the smallest meaningful subset and document why.

- [ ] **Step 3: Capture the exact baseline packaging inputs**

Record the current `deploy/op/contract.yaml`, `Dockerfile.goreleaser`, and any existing build helper scripts so later diffs are intentional rather than ad hoc.

### Task 3: Add the Host-Build Artifact Pipeline in Sub2API

**Files:**
- Create: `/root/work/sub2api/<worktree>/deploy/build-runtime-artifacts.sh`
- Modify: `/root/work/sub2api/<worktree>/Makefile`
- Modify: `/root/work/sub2api/<worktree>/deploy/README.md`
- Test/Verify: command-level smoke verification in the sub2api worktree

- [ ] **Step 1: Write the failing verification target**

Add or update a lightweight script invocation target in `Makefile` or a documented command path that expects a new output directory such as `dist/oplinux/` to exist after the host build runs.

- [ ] **Step 2: Run the verification command to confirm it fails first**

Run:

```bash
wsl.exe -u root -e bash -lc 'cd /root/work/sub2api/<worktree> && bash deploy/build-runtime-artifacts.sh'
```

Expected:

- Failure because the script does not exist yet.

- [ ] **Step 3: Implement the host-build script with the minimal required behavior**

Implement `deploy/build-runtime-artifacts.sh` to:

- install or reuse frontend dependencies with `pnpm --dir frontend install --frozen-lockfile`
- build frontend assets
- run `go mod download` in `backend`
- build the embedded backend binary
- recreate `dist/oplinux/`
- copy the runtime binary and required fallback resources into `dist/oplinux/`

Keep the script deterministic, ASCII-only, and explicit about required paths.

- [ ] **Step 4: Run the host-build command to verify it now passes**

Run:

```bash
wsl.exe -u root -e bash -lc 'cd /root/work/sub2api/<worktree> && bash deploy/build-runtime-artifacts.sh'
```

Expected:

- `dist/oplinux/` exists with the compiled server binary and pricing fallback resources.

- [ ] **Step 5: Commit the host-build pipeline**

```bash
wsl.exe -u root -e bash -lc 'cd /root/work/sub2api/<worktree> && git add deploy/build-runtime-artifacts.sh Makefile deploy/README.md dist/.gitignore && git commit -m "feat: add host-built runtime artifacts"'
```

### Task 4: Switch Sub2API to Runtime-Only Image Packaging

**Files:**
- Create or Modify: `/root/work/sub2api/<worktree>/deploy/Dockerfile.runtime`
- Modify: `/root/work/sub2api/<worktree>/Dockerfile.goreleaser` (if reused instead of a new file)
- Create: `/root/work/sub2api/<worktree>/deploy/package-runtime-image.sh`
- Modify: `/root/work/sub2api/<worktree>/deploy/build_image.sh`
- Modify: `/root/work/sub2api/<worktree>/deploy/op/contract.yaml`
- Test/Verify: runtime image build command in the sub2api worktree

- [ ] **Step 1: Write the failing verification for runtime-only packaging**

Update the intended packaging entrypoint so it expects:

- a runtime-only Dockerfile
- a script command `bash deploy/package-runtime-image.sh`
- no Docker-internal source build path as the formal contract entry

- [ ] **Step 2: Run the packaging command to verify it fails before implementation**

Run:

```bash
wsl.exe -u root -e bash -lc 'cd /root/work/sub2api/<worktree> && IMAGE_TAG=test bash deploy/package-runtime-image.sh'
```

Expected:

- Failure because the package script or runtime Dockerfile is not yet present.

- [ ] **Step 3: Implement the runtime packaging assets**

Implement a runtime-only Dockerfile and `deploy/package-runtime-image.sh` so the packaging path:

- calls `deploy/build-runtime-artifacts.sh`
- builds `sub2api-prod:${IMAGE_TAG}`
- copies only `dist/oplinux/` artifacts plus runtime scripts/resources
- preserves existing runtime dependencies, healthcheck, non-root user, and `docker-entrypoint.sh`

Update `deploy/build_image.sh` to align with the new formal path instead of the old source-build Dockerfile.

- [ ] **Step 4: Update the formal contract to use the script entrypoint**

Change `deploy/op/contract.yaml` so:

- `artifact.build_command` becomes `bash deploy/package-runtime-image.sh`
- `image_name` and tagging behavior remain compatible with OP_Linux

- [ ] **Step 5: Run the packaging command and verify the image builds**

Run:

```bash
wsl.exe -u root -e bash -lc 'cd /root/work/sub2api/<worktree> && IMAGE_TAG=test bash deploy/package-runtime-image.sh'
```

Expected:

- The image `sub2api-prod:test` is built successfully.
- No Docker stage performs source compilation.

- [ ] **Step 6: Commit the runtime-only packaging switch**

```bash
wsl.exe -u root -e bash -lc 'cd /root/work/sub2api/<worktree> && git add deploy/Dockerfile.runtime Dockerfile.goreleaser deploy/package-runtime-image.sh deploy/build_image.sh deploy/op/contract.yaml && git commit -m "feat: package runtime images from host-built artifacts"'
```

### Task 5: Encode the Standard Path in OP_Linux Docs

**Files:**
- Modify: `/root/work/OP_Linux/.worktrees/codex-host-runtime-packaging/docs/architecture/op-linux-app-collaboration.md`
- Modify: `/root/work/OP_Linux/.worktrees/codex-host-runtime-packaging/docs/runbooks/app-project-delivery-workflow.md`
- Test/Verify: targeted grep/readback plus related `pytest` coverage

- [ ] **Step 1: Write the failing documentation/test expectation**

Add or update an OP_Linux test or fixture expectation so the contract example and runbook references no longer present `docker build -f deploy/Dockerfile ...` as the preferred formal path for Docker apps.

- [ ] **Step 2: Run the targeted test to verify it fails**

Run:

```bash
wsl.exe -u root -e bash -lc 'cd /root/work/OP_Linux/.worktrees/codex-host-runtime-packaging && uv run python -m pytest tests/test_app_cli.py -q -k contract'
```

Expected:

- The new documentation-aligned expectation fails before the docs/examples are updated.

- [ ] **Step 3: Update the architecture doc and runbook**

Document that Docker applications should:

- build runtime artifacts on WSL first
- package via a runtime-only Dockerfile
- point `artifact.build_command` at a repo-local script such as `bash deploy/package-runtime-image.sh`

Keep the official SCP / `docker save` / `docker load` production chain unchanged.

- [ ] **Step 4: Re-run the targeted test and documentation checks**

Run:

```bash
wsl.exe -u root -e bash -lc 'cd /root/work/OP_Linux/.worktrees/codex-host-runtime-packaging && uv run python -m pytest tests/test_app_cli.py -q -k contract'
wsl.exe -u root -e bash -lc 'cd /root/work/OP_Linux/.worktrees/codex-host-runtime-packaging && rg -n "package-runtime-image|宿主机预编译|runtime image" docs/architecture/op-linux-app-collaboration.md docs/runbooks/app-project-delivery-workflow.md'
```

Expected:

- New expectations pass.
- The docs explicitly describe the standard host-build packaging path.

- [ ] **Step 5: Commit the OP_Linux documentation updates**

```bash
wsl.exe -u root -e bash -lc 'cd /root/work/OP_Linux/.worktrees/codex-host-runtime-packaging && git add docs/architecture/op-linux-app-collaboration.md docs/runbooks/app-project-delivery-workflow.md tests/test_app_cli.py && git commit -m "docs: standardize host-built runtime packaging"'
```

### Task 6: End-to-End Verification and Handoff

**Files:**
- Verify: `/root/work/sub2api/<worktree>/deploy/op/contract.yaml`
- Verify: `/root/work/OP_Linux/.worktrees/codex-host-runtime-packaging/ops/cli/apps.py`
- Verify: `/root/work/OP_Linux/.worktrees/codex-host-runtime-packaging/docs/architecture/op-linux-app-collaboration.md`
- Verify: `/root/work/OP_Linux/.worktrees/codex-host-runtime-packaging/docs/runbooks/app-project-delivery-workflow.md`

- [ ] **Step 1: Run the final OP_Linux verification set**

Run:

```bash
wsl.exe -u root -e bash -lc 'cd /root/work/OP_Linux/.worktrees/codex-host-runtime-packaging && uv run python -m pytest tests/test_app_cli.py -q'
```

Expected:

- All tests related to this feature pass.
- The three pre-existing `tenant_resources` failures may remain as known baseline noise unless they unexpectedly change.

- [ ] **Step 2: Run the final sub2api packaging smoke checks**

Run:

```bash
wsl.exe -u root -e bash -lc 'cd /root/work/sub2api/<worktree> && bash deploy/build-runtime-artifacts.sh'
wsl.exe -u root -e bash -lc 'cd /root/work/sub2api/<worktree> && IMAGE_TAG=verify bash deploy/package-runtime-image.sh'
wsl.exe -u root -e bash -lc 'docker image inspect sub2api-prod:verify >/dev/null'
```

Expected:

- Artifacts build successfully.
- Runtime image builds successfully.
- The resulting image is locally inspectable.

- [ ] **Step 3: Verify OP_Linux can execute the contract build command**

Run:

```bash
wsl.exe -u root -e bash -lc 'cd /root/work/OP_Linux/.worktrees/codex-host-runtime-packaging && uv run python -m ops.cli app build-artifact --contract /root/work/sub2api/<worktree>/deploy/op/contract.yaml --repo-root /root/work/OP_Linux --image-tag verify --dry-run'
```

Expected:

- The dry-run output shows the new script-based `build_command`.

- [ ] **Step 4: Summarize migration guidance for future Docker projects**

Document in the final handoff that new Docker applications should replicate:

- `deploy/build-runtime-artifacts.sh`
- `deploy/package-runtime-image.sh`
- runtime-only Dockerfile
- script-based `artifact.build_command`

- [ ] **Step 5: Prepare the final review-ready state**

```bash
wsl.exe -u root -e bash -lc 'cd /root/work/OP_Linux/.worktrees/codex-host-runtime-packaging && git status --short'
wsl.exe -u root -e bash -lc 'cd /root/work/sub2api/<worktree> && git status --short'
```

Expected:

- Only intentional changes remain in each worktree.
