# Sub2API Formal Surface Retirement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 分三阶段把 `sub2api` 收口成只负责代码与交付资产的应用仓库，并把 `OP_Linux` 中 `sub2api` 的 app-resource / 文档 / compat 暴露面彻底收口到 formal app delivery surface。

**Architecture:** 先在 `/root/work/sub2api` 硬切 active surface，移除 installer / systemd / generic production deploy 残面，同时用 repo-local shell 校验脚本冻结允许存在的 active 文件集合。然后在 `/root/work/OP_Linux` 抽出共享 host-first app-resource path helper，迁移 registry、inventory、runtime-env projection 与摘要投影，再用 formal refresh commands 回写 tracked artifacts。最后只在 active docs 和 real-contract 约束层保留 formal-only 语义，让 compat helper 退回 archive / provider-debug 角色。

**Tech Stack:** Bash, Markdown, Python 3, `pytest`, `rg`, `git worktree`, `uv run python -m ops.cli ...`

---

## File Map

- `/root/work/sub2api/README.md`
  仓库主入口。必须移除 active systemd / installer / generic self-hosted production 叙事，只保留开发、构建、合同、OP_Linux handoff。
- `/root/work/sub2api/deploy/README.md`
  deploy 目录说明。必须改成 retained build/dev assets 索引，不再把 Binary Install / Docker one-click deploy 当成 active 方法。
- `/root/work/sub2api/docs/README.md`
  docs 主入口。必须只把 active 面指向 `docs/owner/`、`docs/archive/` 和 `docs/OP_LINUX_DEPLOYMENT.*.md`，不再为 retired deploy surface 留活跃入口。
- `/root/work/sub2api/docs/owner/README.md`
  owner/operator 导航。必须明确 formal deploy 只在 `/root/work/OP_Linux`，active tree 不再保留 installer / systemd。
- `/root/work/sub2api/docs/archive/README.md`
  archive 总入口。需要新增对 retired self-hosted / installer 历史面的索引。
- `/root/work/sub2api/docs/archive/self-hosted-legacy.md`
  新建的 archive 说明。记录这轮退场的 installer / systemd / generic production deploy 资产，避免历史上下文完全丢失。
- `/root/work/sub2api/tools/git/test-active-formal-surface.sh`
  新建的 repo-level shell 校验。冻结 `sub2api` active tree 允许存在的 deploy 面，防止旧 installer/systemd 资产回流。
- `/root/work/sub2api/deploy/install.sh`
  退场文件，必须从 active tree 删除。
- `/root/work/sub2api/deploy/install-datamanagementd.sh`
  退场文件，必须从 active tree 删除。
- `/root/work/sub2api/deploy/sub2api.service`
  退场文件，必须从 active tree 删除。
- `/root/work/sub2api/deploy/sub2api-datamanagementd.service`
  退场文件，必须从 active tree 删除。
- `/root/work/sub2api/deploy/docker-deploy.sh`
  退场文件，必须从 active tree 删除。
- `/root/work/sub2api/deploy/build_image.sh`
  退场文件，必须从 active tree 删除。
- `/root/work/sub2api/deploy/Caddyfile`
  退场文件，必须从 active tree 删除。
- `/root/work/sub2api/deploy/DOCKER.md`
  退场文件，必须从 active tree 删除。
- `/root/work/sub2api/deploy/prod`
  已退役目录。若仍有 tracked `dist/` 或 `tmp/` 残留，必须整体退出 active tree。
- `/root/work/OP_Linux/.worktrees/sub2api-formal-surface-phased/ops/domain/app/resource_paths.py`
  新建的 shared helper。统一 host-first secrets root、canonical relative path、secret scope root 和 path normalization。
- `/root/work/OP_Linux/.worktrees/sub2api-formal-surface-phased/ops/cli/app_resource_state.py`
  现有 app-resource state helper。必须改为使用 shared host-first path helper，并更新 secret scope / error message。
- `/root/work/OP_Linux/.worktrees/sub2api-formal-surface-phased/ops/domain/app/secrets_lifecycle.py`
  app-resource secret allocation/retirement。必须改为生成 `secrets/hosts/<target>/apps/<app>/resources/*.env`。
- `/root/work/OP_Linux/.worktrees/sub2api-formal-surface-phased/ops/domain/app/lifecycle.py`
  formal onboarding/offboarding/app-resource registry helper。必须改 canonical secret file list 与 fallback secret root。
- `/root/work/OP_Linux/.worktrees/sub2api-formal-surface-phased/ops/domain/projection/runtime_env.py`
  runtime env projection。必须按新的 host-first secret path 校验 registry entry。
- `/root/work/OP_Linux/.worktrees/sub2api-formal-surface-phased/ops/cli/apps.py`
  app CLI façade。必须去掉内部 duplicate path builder，并改用 shared helper。
- `/root/work/OP_Linux/.worktrees/sub2api-formal-surface-phased/README.md`
  顶层 active docs。必须继续保持 host-first 口径，并在 app-resource surface 上不再让 compat path 发声。
- `/root/work/OP_Linux/.worktrees/sub2api-formal-surface-phased/docs/runbooks/app-project-delivery-workflow.md`
  active workflow。必须把 app-resource 真源收口到 `secrets/hosts/<target>/apps/<app>/resources/`。
- `/root/work/OP_Linux/.worktrees/sub2api-formal-surface-phased/docs/runbooks/prod0-main-governance.md`
  prod0 host runbook。必须停止把 `secrets/app-resources/...` 描述成正式默认路径。
- `/root/work/OP_Linux/.worktrees/sub2api-formal-surface-phased/docs/runbooks/docker-host-runtime-packaging-template.md`
  docker app onboarding template。必须把 rollback 示例从 compat rollback 改成 `kind: none`。
- `/root/work/OP_Linux/.worktrees/sub2api-formal-surface-phased/docs/runbooks/onepanel-app-lifecycle.md`
  compat helper 说明。必须明确 formal catalog apps 不把它当执行入口。
- `/root/work/OP_Linux/.worktrees/sub2api-formal-surface-phased/docs/runbooks/powershell-wsl-remote-bash.md`
  compat helper runbook。必须继续保留 compat 说明，但不再暗示 formal app 依赖这些 helper。
- `/root/work/OP_Linux/.worktrees/sub2api-formal-surface-phased/inventory/servers/{wsl,prod0-main,prod2-main}/inventory.json`
  tracked inventory。需要通过 formal refresh commands 回写新的 `secret_file` 路径。
- `/root/work/OP_Linux/.worktrees/sub2api-formal-surface-phased/inventory/servers/{wsl,prod0-main,prod2-main}/app-resources.json`
  tracked app-resource registry。需要通过 `app resource refresh-ledger` 与 code migration 一起回写。
- `/root/work/OP_Linux/.worktrees/sub2api-formal-surface-phased/inventory/servers/{wsl,prod0-main,prod2-main}/README.md`
  target summary。必须不再打印 compat canonical path。
- `/root/work/OP_Linux/.worktrees/sub2api-formal-surface-phased/inventory/servers/{prod0-main,prod2-main}/app_resources.md`
  app-resource Markdown 摘要。必须切换到 host-first secret reference。
- `/root/work/OP_Linux/.worktrees/sub2api-formal-surface-phased/tests/app_resource_path_fixtures.py`
  新建的测试 helper。统一测试里对 host-first app-resource relative/root path 的生成。
- `/root/work/OP_Linux/.worktrees/sub2api-formal-surface-phased/tests/test_app_resource_object_cli.py`
  app-resource object tests。必须用 shared test helper 替换 compat path fixture。
- `/root/work/OP_Linux/.worktrees/sub2api-formal-surface-phased/tests/test_app_resource_cli.py`
  app-resource CLI tests。必须用 shared test helper 替换 compat path fixture。
- `/root/work/OP_Linux/.worktrees/sub2api-formal-surface-phased/tests/test_projection_runtime_env_cli.py`
  runtime-env projection tests。必须用 shared test helper 和 host-first path。
- `/root/work/OP_Linux/.worktrees/sub2api-formal-surface-phased/tests/test_app_cli.py`
  app delivery / inventory / summary tests。必须把 app-resource path fixture 改成 host-first，并继续验证 summary 不暴露 compat path。
- `/root/work/OP_Linux/.worktrees/sub2api-formal-surface-phased/tests/test_prod0_audit.py`
  prod0 audit tests。必须更新 formal app resource secret_file 路径与 drift fixtures。
- `/root/work/OP_Linux/.worktrees/sub2api-formal-surface-phased/tests/test_docs_no_legacy_terms.py`
  active doc contract tests。必须加入对 host-first resource path 和 rollback `kind: none` 示例的断言。
- `/root/work/OP_Linux/.worktrees/sub2api-formal-surface-phased/tests/test_wsl_first_docs.py`
  compat helper docs tests。必须继续保留 compat helper 语义，但不再让 formal app 以它们为默认入口。
- `/root/work/OP_Linux/.worktrees/sub2api-formal-surface-phased/tests/test_app_object_cli.py`
  real contract verification tests。必须冻结 `sub2api` / `newapi` / `sub2apipay` real contracts 的 `rollback.previous_control_plane.kind == none`。

## Task 1: 建立隔离工作区并冻结 `sub2api` Phase 1 失败面

**Files:**
- Create: `/root/work/sub2api/tools/git/test-active-formal-surface.sh`
- Test: `/root/work/sub2api/tools/git/test-active-formal-surface.sh`

- [ ] **Step 1: 创建 `sub2api` 的实现 worktree，并确认 OP_Linux 计划 worktree 已就绪**

Run:

```bash
cd /root/work/sub2api
make worktree-init BRANCH=codex/sub2api-phase1-formal-surface BASE=main CLEANUP_ON_FAIL=1
cd /root/work/sub2api/.worktrees/codex/sub2api-phase1-formal-surface
git branch --show-current

cd /root/work/OP_Linux/.worktrees/sub2api-formal-surface-phased
git branch --show-current
```

Expected:

- `/root/work/sub2api/.worktrees/codex/sub2api-phase1-formal-surface` 当前分支是 `codex/sub2api-phase1-formal-surface`
- `/root/work/OP_Linux/.worktrees/sub2api-formal-surface-phased` 当前分支是 `codex/sub2api-formal-surface-phased`

- [ ] **Step 2: 写出 `sub2api` active surface 的失败测试脚本**

Create `/root/work/sub2api/.worktrees/codex/sub2api-phase1-formal-surface/tools/git/test-active-formal-surface.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

forbidden_files=(
  "deploy/install.sh"
  "deploy/install-datamanagementd.sh"
  "deploy/sub2api.service"
  "deploy/sub2api-datamanagementd.service"
  "deploy/docker-deploy.sh"
  "deploy/build_image.sh"
  "deploy/Caddyfile"
  "deploy/DOCKER.md"
)

required_patterns=(
  "Formal production control plane now lives in `/root/work/OP_Linux`"
  "deploy/op/contract.wsl.yaml"
  "deploy/op/contract.yaml"
  "deploy/op/contract.prod2.yaml"
)

forbidden_patterns=(
  "curl -sSL https://raw.githubusercontent.com/.*/deploy/install.sh"
  "sudo systemctl start sub2api"
  "Binary Install"
  "docker-deploy.sh"
  "Support rollback if needed"
)

docs=(
  "${repo_root}/README.md"
  "${repo_root}/deploy/README.md"
  "${repo_root}/docs/README.md"
  "${repo_root}/docs/owner/README.md"
)

echo "[check] retired installer/systemd assets must not stay tracked"
for path in "${forbidden_files[@]}"; do
  if git -C "${repo_root}" ls-files --error-unmatch "${path}" >/dev/null 2>&1; then
    echo "FAIL: retired active-surface file still tracked: ${path}" >&2
    exit 1
  fi
done

echo "[check] deploy/prod must not stay tracked"
if git -C "${repo_root}" ls-files 'deploy/prod/**' | grep -q .; then
  echo "FAIL: deploy/prod still contains tracked files" >&2
  git -C "${repo_root}" ls-files 'deploy/prod/**'
  exit 1
fi

echo "[check] required OP_Linux handoff markers must stay present"
for pattern in "${required_patterns[@]}"; do
  if ! rg -n "${pattern}" "${docs[@]}" >/tmp/test-active-formal-surface.required.out 2>/dev/null; then
    echo "FAIL: missing required pattern '${pattern}'" >&2
    exit 1
  fi
done

echo "[check] active docs must not advertise retired production paths"
for pattern in "${forbidden_patterns[@]}"; do
  if rg -n "${pattern}" "${docs[@]}" >/tmp/test-active-formal-surface.forbidden.out 2>/dev/null; then
    echo "FAIL: found forbidden pattern '${pattern}'" >&2
    cat /tmp/test-active-formal-surface.forbidden.out
    exit 1
  fi
done

echo "PASS: sub2api active formal surface checks passed"
```

- [ ] **Step 3: 跑脚本确认 Phase 1 基线先失败**

Run:

```bash
cd /root/work/sub2api/.worktrees/codex/sub2api-phase1-formal-surface
bash tools/git/test-active-formal-surface.sh
```

Expected:

- 失败点至少包含 tracked `deploy/install.sh`、`deploy/docker-deploy.sh` 或 `deploy/prod/**`
- 失败来自当前 active tree 仍保留 retired assets，而不是脚本语法错误

- [ ] **Step 4: 先做脚本语法验证，防止后续把测试脚本本身写坏**

Run:

```bash
cd /root/work/sub2api/.worktrees/codex/sub2api-phase1-formal-surface
bash -n tools/git/test-active-formal-surface.sh
```

Expected:

- 无输出

## Task 2: 实施 `sub2api` Phase 1 收缩

**Files:**
- Modify: `/root/work/sub2api/.worktrees/codex/sub2api-phase1-formal-surface/README.md`
- Modify: `/root/work/sub2api/.worktrees/codex/sub2api-phase1-formal-surface/deploy/README.md`
- Modify: `/root/work/sub2api/.worktrees/codex/sub2api-phase1-formal-surface/docs/README.md`
- Modify: `/root/work/sub2api/.worktrees/codex/sub2api-phase1-formal-surface/docs/owner/README.md`
- Modify: `/root/work/sub2api/.worktrees/codex/sub2api-phase1-formal-surface/docs/archive/README.md`
- Create: `/root/work/sub2api/.worktrees/codex/sub2api-phase1-formal-surface/docs/archive/self-hosted-legacy.md`
- Delete: `/root/work/sub2api/.worktrees/codex/sub2api-phase1-formal-surface/deploy/install.sh`
- Delete: `/root/work/sub2api/.worktrees/codex/sub2api-phase1-formal-surface/deploy/install-datamanagementd.sh`
- Delete: `/root/work/sub2api/.worktrees/codex/sub2api-phase1-formal-surface/deploy/sub2api.service`
- Delete: `/root/work/sub2api/.worktrees/codex/sub2api-phase1-formal-surface/deploy/sub2api-datamanagementd.service`
- Delete: `/root/work/sub2api/.worktrees/codex/sub2api-phase1-formal-surface/deploy/docker-deploy.sh`
- Delete: `/root/work/sub2api/.worktrees/codex/sub2api-phase1-formal-surface/deploy/build_image.sh`
- Delete: `/root/work/sub2api/.worktrees/codex/sub2api-phase1-formal-surface/deploy/Caddyfile`
- Delete: `/root/work/sub2api/.worktrees/codex/sub2api-phase1-formal-surface/deploy/DOCKER.md`
- Delete: tracked files under `/root/work/sub2api/.worktrees/codex/sub2api-phase1-formal-surface/deploy/prod/`
- Test: `/root/work/sub2api/.worktrees/codex/sub2api-phase1-formal-surface/tools/git/test-active-formal-surface.sh`

- [ ] **Step 1: 把根 `README.md` 改成“开发/构建/合同/OP_Linux handoff”入口**

在 `/root/work/sub2api/.worktrees/codex/sub2api-phase1-formal-surface/README.md` 的 active deployment 段落替换为：

```markdown
## Repository Role

The formal production control plane for this fork lives in `/root/work/OP_Linux`.

This repository keeps only:

- application code and tests
- runtime build assets
- development Docker assets
- non-sensitive OP handoff contracts under `deploy/op/`
- non-sensitive deployment summaries written back by OP_Linux

For formal production work:

- prepare code, tests, and runtime image inputs here
- run onboarding, deploy, rollback, verify, inventory refresh, and doc-sync from `/root/work/OP_Linux`
- treat `docs/archive/` as the only retained history surface for retired self-hosted and systemd entrypoints
```

删除当前仍在 active README 里的这些段落：

```markdown
### Method 1: Script Installation (Recommended)
### Method 2: Docker Compose (Recommended)
```

以及所有 `systemctl`、`install.sh`、网页升级/rollback 说明。

- [ ] **Step 2: 把 `deploy/README.md` 改成 retained assets 索引，而不是 active deployment guide**

将 `/root/work/sub2api/.worktrees/codex/sub2api-phase1-formal-surface/deploy/README.md` 的方法表替换为：

```markdown
# Sub2API Build And Handoff Assets

> **Formal production control plane:** `/root/work/OP_Linux` owns production deploy, verify, rollback, inventory refresh, and doc-sync.

## Retained Active Assets

| Path | Role |
| --- | --- |
| `build-runtime-artifacts.sh` | Build runtime artifacts on the WSL host |
| `package-runtime-image.sh` | Package `sub2api-prod:<tag>` from runtime artifacts |
| `Dockerfile.runtime` | Runtime-only image build |
| `docker-entrypoint.sh` | Runtime container entrypoint |
| `op/contract.wsl.yaml` | WSL contract consumed by OP_Linux |
| `op/contract.yaml` | prod0-main contract consumed by OP_Linux |
| `op/contract.prod2.yaml` | prod2-main contract consumed by OP_Linux |
| `op/runtime.env.example` | Non-sensitive runtime env template |
| `docker-compose.dev.yml` / `docker-compose.local.yml` | Dev-only local Docker assets; not formal production deploy entrypoints |

## Retired Active Assets

Installer, systemd, generic self-hosted production deploy, and release tarball surfaces have moved out of the active tree. Historical context is retained only under `docs/archive/`.
```

- [ ] **Step 3: 新增 archive 说明，并更新 docs 导航**

Create `/root/work/sub2api/.worktrees/codex/sub2api-phase1-formal-surface/docs/archive/self-hosted-legacy.md`:

```markdown
# Retired Self-Hosted And Installer Surface

This file records the active-surface retirement completed on 2026-04-08.

Retired from the active tree:

- `deploy/install.sh`
- `deploy/install-datamanagementd.sh`
- `deploy/sub2api.service`
- `deploy/sub2api-datamanagementd.service`
- `deploy/docker-deploy.sh`
- `deploy/build_image.sh`
- `deploy/Caddyfile`
- `deploy/DOCKER.md`
- tracked `deploy/prod/**`

Reason:

- formal production onboarding/deploy/rollback/verify now belong only to `/root/work/OP_Linux`
- this repository keeps code, tests, build assets, development Docker assets, and `deploy/op/` contracts
```

在以下文件加入 archive 指针：

```markdown
<!-- /root/work/sub2api/.worktrees/codex/sub2api-phase1-formal-surface/docs/README.md -->
- `docs/archive/self-hosted-legacy.md`

<!-- /root/work/sub2api/.worktrees/codex/sub2api-phase1-formal-surface/docs/owner/README.md -->
- Retired self-hosted/install surface: `docs/archive/self-hosted-legacy.md`

<!-- /root/work/sub2api/.worktrees/codex/sub2api-phase1-formal-surface/docs/archive/README.md -->
- `docs/archive/self-hosted-legacy.md`
```

- [ ] **Step 4: 删除 retired active assets**

Run:

```bash
cd /root/work/sub2api/.worktrees/codex/sub2api-phase1-formal-surface
git rm deploy/install.sh \
  deploy/install-datamanagementd.sh \
  deploy/sub2api.service \
  deploy/sub2api-datamanagementd.service \
  deploy/docker-deploy.sh \
  deploy/build_image.sh \
  deploy/Caddyfile \
  deploy/DOCKER.md
git rm -r deploy/prod
```

Expected:

- `git status --short` 只显示本任务涉及的 docs 改动和 delete 记录

- [ ] **Step 5: 跑 Phase 1 最小验证**

Run:

```bash
cd /root/work/sub2api/.worktrees/codex/sub2api-phase1-formal-surface
bash tools/git/test-active-formal-surface.sh
bash -n deploy/package-runtime-image.sh
rg -n 'install.sh|systemctl start sub2api|docker-deploy.sh|Binary Install' README.md deploy/README.md docs/README.md docs/owner/README.md -g '!docs/archive/**'
```

Expected:

- `test-active-formal-surface.sh` 输出 `PASS`
- `bash -n deploy/package-runtime-image.sh` 无输出
- 最后的 `rg` 无命中

- [ ] **Step 6: 提交 Phase 1**

```bash
cd /root/work/sub2api/.worktrees/codex/sub2api-phase1-formal-surface
git add README.md deploy/README.md docs/README.md docs/owner/README.md docs/archive/README.md docs/archive/self-hosted-legacy.md tools/git/test-active-formal-surface.sh
git commit -m "govern: retire active self-hosted surface"
```

## Task 3: 冻结 Phase 2 的 host-first path 测试

**Files:**
- Create: `/root/work/OP_Linux/.worktrees/sub2api-formal-surface-phased/tests/app_resource_path_fixtures.py`
- Modify: `/root/work/OP_Linux/.worktrees/sub2api-formal-surface-phased/tests/test_app_resource_object_cli.py`
- Modify: `/root/work/OP_Linux/.worktrees/sub2api-formal-surface-phased/tests/test_app_resource_cli.py`
- Modify: `/root/work/OP_Linux/.worktrees/sub2api-formal-surface-phased/tests/test_projection_runtime_env_cli.py`
- Modify: `/root/work/OP_Linux/.worktrees/sub2api-formal-surface-phased/tests/test_app_cli.py`
- Modify: `/root/work/OP_Linux/.worktrees/sub2api-formal-surface-phased/tests/test_prod0_audit.py`

- [ ] **Step 1: 创建统一的 host-first 测试路径 helper**

Create `/root/work/OP_Linux/.worktrees/sub2api-formal-surface-phased/tests/app_resource_path_fixtures.py`:

```python
from __future__ import annotations

from pathlib import Path


def resource_relative(target: str, app: str, kind: str) -> str:
    return f"secrets/hosts/{target}/apps/{app}/resources/{kind}.env"


def resource_root(root: Path, target: str, app: str) -> Path:
    return root / "secrets" / "hosts" / target / "apps" / app / "resources"
```

- [ ] **Step 2: 把 app-resource 相关测试 fixture 全部改成通过 helper 生成路径**

在 `/root/work/OP_Linux/.worktrees/sub2api-formal-surface-phased/tests/test_app_resource_object_cli.py`、`tests/test_app_resource_cli.py`、`tests/test_projection_runtime_env_cli.py`、`tests/test_app_cli.py`、`tests/test_prod0_audit.py` 中加入：

```python
from tests.app_resource_path_fixtures import resource_relative, resource_root
```

并把旧写法：

```python
"secret_file": "secrets/app-resources/prod2-main/sub2api/postgres.env"
resource_root = root / "secrets" / "app-resources" / "prod2-main" / "sub2api"
```

统一替换成：

```python
"secret_file": resource_relative("prod2-main", "sub2api", "postgres")
secret_root = resource_root(root, "prod2-main", "sub2api")
```

并把以下旧 literal 全部替换掉：

```text
secrets/app-resources/prod0-main/sub2api/*.env
secrets/app-resources/prod2-main/sub2api/*.env
secrets/app-resources/wsl/sub2api/*.env
secrets/app-resources/prod0-main/newapi/*.env
secrets/app-resources/prod2-main/newapi/*.env
secrets/app-resources/wsl/newapi/*.env
secrets/app-resources/prod0-main/sub2apipay/postgres.env
```

- [ ] **Step 3: 运行定向测试，确认它们先按“实现未改”失败**

Run:

```bash
cd /root/work/OP_Linux/.worktrees/sub2api-formal-surface-phased
uv run python -m pytest \
  tests/test_app_resource_object_cli.py \
  tests/test_app_resource_cli.py \
  tests/test_projection_runtime_env_cli.py \
  tests/test_prod0_audit.py -q
```

Expected:

- 失败点集中在当前实现仍生成 / 校验 `secrets/app-resources/...`
- 不出现导入错误或 helper 拼写错误

## Task 4: 实施 Phase 2 的 host-first app-resource 路径迁移

**Files:**
- Create: `/root/work/OP_Linux/.worktrees/sub2api-formal-surface-phased/ops/domain/app/resource_paths.py`
- Modify: `/root/work/OP_Linux/.worktrees/sub2api-formal-surface-phased/ops/cli/app_resource_state.py`
- Modify: `/root/work/OP_Linux/.worktrees/sub2api-formal-surface-phased/ops/domain/app/secrets_lifecycle.py`
- Modify: `/root/work/OP_Linux/.worktrees/sub2api-formal-surface-phased/ops/domain/app/lifecycle.py`
- Modify: `/root/work/OP_Linux/.worktrees/sub2api-formal-surface-phased/ops/domain/projection/runtime_env.py`
- Modify: `/root/work/OP_Linux/.worktrees/sub2api-formal-surface-phased/ops/cli/apps.py`

- [ ] **Step 1: 新建 shared resource path helper**

Create `/root/work/OP_Linux/.worktrees/sub2api-formal-surface-phased/ops/domain/app/resource_paths.py`:

```python
from __future__ import annotations

from pathlib import Path


def git_common_root(repo_root: Path) -> Path | None:
    git_entry = repo_root / ".git"
    if git_entry.is_dir():
        return repo_root
    if not git_entry.is_file():
        return None
    content = git_entry.read_text(encoding="utf-8").strip()
    prefix = "gitdir:"
    if not content.startswith(prefix):
        return None
    git_dir = Path(content[len(prefix) :].strip())
    if not git_dir.is_absolute():
        git_dir = (repo_root / git_dir).resolve()
    if len(git_dir.parts) >= 3 and git_dir.parent.name == "worktrees" and git_dir.parent.parent.name == ".git":
        return git_dir.parents[2]
    return None


def secrets_root(repo_root: Path) -> Path:
    direct = repo_root / "secrets"
    if direct.exists():
        return direct
    common_root = git_common_root(repo_root)
    if common_root is not None:
        common_secrets = common_root / "secrets"
        if common_secrets.exists():
            return common_secrets
    return direct


def app_resource_secret_dir(repo_root: Path, target: str, app_id: str) -> Path:
    return secrets_root(repo_root) / "hosts" / target / "apps" / app_id / "resources"


def app_resource_secret_relative(target: str, app_id: str, kind: str) -> str:
    return f"secrets/hosts/{target}/apps/{app_id}/resources/{kind}.env"


def resolve_secret_file_path(repo_root: Path, secret_file: str) -> Path:
    candidate = Path(secret_file)
    if candidate.is_absolute():
        return candidate.resolve(strict=False)
    if candidate.parts and candidate.parts[0] == "secrets":
        return (secrets_root(repo_root) / Path(*candidate.parts[1:])).resolve(strict=False)
    return (repo_root / candidate).resolve(strict=False)
```

- [ ] **Step 2: 把 app-resource state helper 改成使用 shared helper**

在 `/root/work/OP_Linux/.worktrees/sub2api-formal-surface-phased/ops/cli/app_resource_state.py` 替换内部 `_git_common_root`、`_secrets_root`、`app_resource_secret_dir`、`resolve_secret_file_path` 实现，改为：

```python
from ops.domain.app.resource_paths import (
    app_resource_secret_dir,
    app_resource_secret_relative,
    resolve_secret_file_path,
    secrets_root,
)
```

并把 scope 错误信息：

```python
"message": "app resource registry secret_files must stay within secrets/hosts/<target>/apps/<app>/resources/",
```

替换旧的 `secrets/app-resources/<target>/<app>/` 文案。

- [ ] **Step 3: 把 lifecycle、secrets_lifecycle、runtime_env、apps façade 的 canonical path 统一接到 helper**

把以下旧逻辑：

```python
f"secrets/app-resources/{target}/{app}/{kind}.env"
repo_root / "secrets" / "app-resources" / target / app
expected_secret_file = f"secrets/app-resources/{target}/{app_id}/{kind}.env"
```

统一替换成：

```python
from ops.domain.app.resource_paths import app_resource_secret_dir, app_resource_secret_relative

app_resource_secret_relative(target, app, kind)
str(app_resource_secret_dir(repo_root, target, app))
expected_secret_file = app_resource_secret_relative(target, app_id, kind)
```

具体修改点：

- `/root/work/OP_Linux/.worktrees/sub2api-formal-surface-phased/ops/domain/app/secrets_lifecycle.py`
- `/root/work/OP_Linux/.worktrees/sub2api-formal-surface-phased/ops/domain/app/lifecycle.py`
- `/root/work/OP_Linux/.worktrees/sub2api-formal-surface-phased/ops/domain/projection/runtime_env.py`
- `/root/work/OP_Linux/.worktrees/sub2api-formal-surface-phased/ops/cli/apps.py`

- [ ] **Step 4: 跑 Phase 2 代码层测试，确认 host-first migration 通过**

Run:

```bash
cd /root/work/OP_Linux/.worktrees/sub2api-formal-surface-phased
uv run python -m pytest \
  tests/test_app_resource_object_cli.py \
  tests/test_app_resource_cli.py \
  tests/test_projection_runtime_env_cli.py \
  tests/test_app_cli.py \
  tests/test_prod0_audit.py -q
```

Expected:

- 所有测试通过
- `rg -n "secrets/app-resources/" ops tests/test_app_resource_object_cli.py tests/test_app_resource_cli.py tests/test_projection_runtime_env_cli.py tests/test_prod0_audit.py` 只允许命中刻意保留的 compat explanation，不允许命中 canonical path builder

## Task 5: 回写 tracked inventory / summaries，并完成 Phase 2 文档收口

**Files:**
- Modify: `/root/work/OP_Linux/.worktrees/sub2api-formal-surface-phased/README.md`
- Modify: `/root/work/OP_Linux/.worktrees/sub2api-formal-surface-phased/docs/runbooks/app-project-delivery-workflow.md`
- Modify: `/root/work/OP_Linux/.worktrees/sub2api-formal-surface-phased/docs/runbooks/prod0-main-governance.md`
- Modify: `/root/work/OP_Linux/.worktrees/sub2api-formal-surface-phased/inventory/servers/wsl/inventory.json`
- Modify: `/root/work/OP_Linux/.worktrees/sub2api-formal-surface-phased/inventory/servers/wsl/app-resources.json`
- Modify: `/root/work/OP_Linux/.worktrees/sub2api-formal-surface-phased/inventory/servers/wsl/README.md`
- Modify: `/root/work/OP_Linux/.worktrees/sub2api-formal-surface-phased/inventory/servers/prod0-main/inventory.json`
- Modify: `/root/work/OP_Linux/.worktrees/sub2api-formal-surface-phased/inventory/servers/prod0-main/app-resources.json`
- Modify: `/root/work/OP_Linux/.worktrees/sub2api-formal-surface-phased/inventory/servers/prod0-main/README.md`
- Modify: `/root/work/OP_Linux/.worktrees/sub2api-formal-surface-phased/inventory/servers/prod0-main/app_resources.md`
- Modify: `/root/work/OP_Linux/.worktrees/sub2api-formal-surface-phased/inventory/servers/prod2-main/inventory.json`
- Modify: `/root/work/OP_Linux/.worktrees/sub2api-formal-surface-phased/inventory/servers/prod2-main/app-resources.json`
- Modify: `/root/work/OP_Linux/.worktrees/sub2api-formal-surface-phased/inventory/servers/prod2-main/README.md`
- Modify: `/root/work/OP_Linux/.worktrees/sub2api-formal-surface-phased/inventory/servers/prod2-main/app_resources.md`

- [ ] **Step 1: 先改 active docs 的 host-first 文案**

在 `/root/work/OP_Linux/.worktrees/sub2api-formal-surface-phased/docs/runbooks/app-project-delivery-workflow.md` 与 `/root/work/OP_Linux/.worktrees/sub2api-formal-surface-phased/docs/runbooks/prod0-main-governance.md` 把旧文案：

```markdown
secrets/app-resources/<target>/<app>/
```

替换成：

```markdown
secrets/hosts/<target>/apps/<app>/resources/
```

并明确：

```markdown
`secrets/services/<app>.<target-scope>.env` 只是 runtime projection，不是 app-resource truth。
```

- [ ] **Step 2: 用 formal refresh commands 回写 tracked artifacts**

Run:

```bash
cd /root/work/OP_Linux/.worktrees/sub2api-formal-surface-phased

for target in wsl prod0-main prod2-main; do
  uv run python -m ops.cli app resource refresh-ledger --target "${target}" --repo-root /root/work/OP_Linux/.worktrees/sub2api-formal-surface-phased --write
done

for pair in \
  "wsl sub2api" \
  "prod0-main sub2api" \
  "prod2-main sub2api" \
  "prod0-main newapi" \
  "prod2-main newapi" \
  "prod0-main sub2apipay"; do
  set -- ${pair}
  uv run python -m ops.cli app delivery inventory-refresh --target "$1" --app "$2" --repo-root /root/work/OP_Linux/.worktrees/sub2api-formal-surface-phased --write
done

for target in wsl prod0-main prod2-main; do
  uv run python -m ops.cli projection ledger refresh --target "${target}" --repo-root /root/work/OP_Linux/.worktrees/sub2api-formal-surface-phased --write
done

for pair in \
  "wsl sub2api" \
  "prod0-main sub2api" \
  "prod2-main sub2api"; do
  set -- ${pair}
  uv run python -m ops.cli app delivery doc-sync --target "$1" --app "$2" --repo-root /root/work/OP_Linux/.worktrees/sub2api-formal-surface-phased --write
done
```

Expected:

- `inventory/servers/{wsl,prod0-main,prod2-main}/inventory.json`、`app-resources.json`、`README.md`、`app_resources.md` 中的 app-resource secret path 已切换到 host-first
- `sub2api` 的 `docs/OP_LINUX_DEPLOYMENT.*.md` 不再打印 `secrets/app-resources/...`

- [ ] **Step 3: 跑 Phase 2 文档与对象面验证**

Run:

```bash
cd /root/work/OP_Linux/.worktrees/sub2api-formal-surface-phased
uv run python -m pytest \
  tests/test_docs_no_legacy_terms.py \
  tests/test_repo_snapshot_contracts.py -q

uv run python -m ops.cli app resource verify --target prod2-main --app sub2api --repo-root /root/work/OP_Linux/.worktrees/sub2api-formal-surface-phased
uv run python -m ops.cli app object verify --target prod2-main --app sub2api --repo-root /root/work/OP_Linux/.worktrees/sub2api-formal-surface-phased
uv run python -m ops.cli app delivery validate-contract --target prod2-main --app sub2api --repo-root /root/work/OP_Linux/.worktrees/sub2api-formal-surface-phased
```

Expected:

- pytest 通过
- 三个 CLI 都返回 `ok: true` 或 `valid: true`

- [ ] **Step 4: 提交 Phase 2**

```bash
cd /root/work/OP_Linux/.worktrees/sub2api-formal-surface-phased
git add ops/domain/app/resource_paths.py ops/cli/app_resource_state.py ops/domain/app/secrets_lifecycle.py ops/domain/app/lifecycle.py ops/domain/projection/runtime_env.py ops/cli/apps.py
git add README.md docs/runbooks/app-project-delivery-workflow.md docs/runbooks/prod0-main-governance.md
git add inventory/servers/wsl inventory/servers/prod0-main inventory/servers/prod2-main
git add tests/app_resource_path_fixtures.py tests/test_app_resource_object_cli.py tests/test_app_resource_cli.py tests/test_projection_runtime_env_cli.py tests/test_app_cli.py tests/test_prod0_audit.py tests/test_docs_no_legacy_terms.py
git commit -m "feat: migrate app resource truth to host-first paths"
```

## Task 6: 收掉 Phase 3 的 active docs / contract template compat 暴露

**Files:**
- Modify: `/root/work/OP_Linux/.worktrees/sub2api-formal-surface-phased/docs/runbooks/docker-host-runtime-packaging-template.md`
- Modify: `/root/work/OP_Linux/.worktrees/sub2api-formal-surface-phased/docs/runbooks/onepanel-app-lifecycle.md`
- Modify: `/root/work/OP_Linux/.worktrees/sub2api-formal-surface-phased/docs/runbooks/powershell-wsl-remote-bash.md`
- Modify: `/root/work/OP_Linux/.worktrees/sub2api-formal-surface-phased/tests/test_docs_no_legacy_terms.py`
- Modify: `/root/work/OP_Linux/.worktrees/sub2api-formal-surface-phased/tests/test_wsl_first_docs.py`
- Modify: `/root/work/OP_Linux/.worktrees/sub2api-formal-surface-phased/tests/test_app_object_cli.py`

- [ ] **Step 1: 先写 Phase 3 的 real-contract 与 docs 失败测试**

在 `/root/work/OP_Linux/.worktrees/sub2api-formal-surface-phased/tests/test_app_object_cli.py` 新增：

```python
    def test_real_formal_catalog_apps_keep_none_previous_control_plane(self) -> None:
        targets = (
            ("prod0-main", "sub2api"),
            ("prod2-main", "sub2api"),
            ("prod0-main", "newapi"),
            ("prod2-main", "newapi"),
            ("prod0-main", "sub2apipay"),
        )
        for target, app in targets:
            with self.subTest(target=target, app=app):
                result = run_cli(
                    "app",
                    "object",
                    "get",
                    "--target",
                    target,
                    "--app",
                    app,
                    "--repo-root",
                    str(REPO_ROOT),
                )
                self.assertEqual(result.returncode, 0, msg=result.stderr)
                payload = json.loads(result.stdout)
                self.assertEqual("none", payload["payload"]["rollback"]["previous_control_plane"]["kind"])
```

在 `/root/work/OP_Linux/.worktrees/sub2api-formal-surface-phased/tests/test_docs_no_legacy_terms.py` 新增断言：

```python
        template_text = (
            REPO_ROOT / "docs" / "runbooks" / "docker-host-runtime-packaging-template.md"
        ).read_text(encoding="utf-8")
        self.assertIn("kind: none", template_text)
        self.assertNotIn("kind: systemd", template_text)
```

- [ ] **Step 2: 改 active docs，让 compat helper 只保留 provider/debug 语义**

把 `/root/work/OP_Linux/.worktrees/sub2api-formal-surface-phased/docs/runbooks/docker-host-runtime-packaging-template.md` 的 rollback 示例：

```yaml
rollback:
  previous_control_plane:
    kind: systemd
```

替换成：

```yaml
rollback:
  previous_control_plane:
    kind: none
```

并在 `/root/work/OP_Linux/.worktrees/sub2api-formal-surface-phased/docs/runbooks/onepanel-app-lifecycle.md` 与 `/root/work/OP_Linux/.worktrees/sub2api-formal-surface-phased/docs/runbooks/powershell-wsl-remote-bash.md` 增加这句：

```markdown
Formal catalog apps with `schema_version: 1` must use `uv run python -m ops.cli app object ...`, `app delivery ...`, `service ...`, and `website ...`; these compat helpers are not the active execution path.
```

- [ ] **Step 3: 跑 Phase 3 文档 / real-contract 验证**

Run:

```bash
cd /root/work/OP_Linux/.worktrees/sub2api-formal-surface-phased
uv run python -m pytest \
  tests/test_app_object_cli.py \
  tests/test_docs_no_legacy_terms.py \
  tests/test_wsl_first_docs.py -q
```

Expected:

- active docs 通过 formal-only 断言
- real catalog apps 的 `previous_control_plane.kind` 都是 `none`

- [ ] **Step 4: 提交 Phase 3**

```bash
cd /root/work/OP_Linux/.worktrees/sub2api-formal-surface-phased
git add docs/runbooks/docker-host-runtime-packaging-template.md docs/runbooks/onepanel-app-lifecycle.md docs/runbooks/powershell-wsl-remote-bash.md
git add tests/test_app_object_cli.py tests/test_docs_no_legacy_terms.py tests/test_wsl_first_docs.py
git commit -m "docs: cut sub2api active compat exposure"
```

## Task 7: 做最终联调验证并准备集成

**Files:**
- Verify only: `/root/work/sub2api/.worktrees/codex/sub2api-phase1-formal-surface`
- Verify only: `/root/work/OP_Linux/.worktrees/sub2api-formal-surface-phased`

- [ ] **Step 1: 跑 `sub2api` 最终最小验证**

Run:

```bash
cd /root/work/sub2api/.worktrees/codex/sub2api-phase1-formal-surface
bash tools/git/test-active-formal-surface.sh
bash -n deploy/package-runtime-image.sh

cd /root/work/OP_Linux
uv run python -m ops.cli app delivery validate-contract --target wsl --app sub2api --repo-root /root/work/OP_Linux
uv run python -m ops.cli app delivery validate-contract --target prod0-main --app sub2api --repo-root /root/work/OP_Linux
uv run python -m ops.cli app delivery validate-contract --target prod2-main --app sub2api --repo-root /root/work/OP_Linux
```

Expected:

- shell checks通过
- 三个 target 的合同校验都返回 `valid: true`

- [ ] **Step 2: 跑 `OP_Linux` 的最终相关测试集合**

Run:

```bash
cd /root/work/OP_Linux/.worktrees/sub2api-formal-surface-phased
uv run python -m pytest \
  tests/test_app_resource_object_cli.py \
  tests/test_app_resource_cli.py \
  tests/test_projection_runtime_env_cli.py \
  tests/test_app_cli.py \
  tests/test_app_object_cli.py \
  tests/test_prod0_audit.py \
  tests/test_docs_no_legacy_terms.py \
  tests/test_wsl_first_docs.py \
  tests/test_repo_snapshot_contracts.py -q
```

Expected:

- 全部通过

- [ ] **Step 3: 跑 formal surface 端到端只读校验**

Run:

```bash
cd /root/work/OP_Linux/.worktrees/sub2api-formal-surface-phased
uv run python -m ops.cli app object search --target prod2-main --app sub2api --repo-root /root/work/OP_Linux/.worktrees/sub2api-formal-surface-phased
uv run python -m ops.cli app object verify --target prod2-main --app sub2api --repo-root /root/work/OP_Linux/.worktrees/sub2api-formal-surface-phased
uv run python -m ops.cli app resource verify --target prod2-main --app sub2api --repo-root /root/work/OP_Linux/.worktrees/sub2api-formal-surface-phased
uv run python -m ops.cli app delivery deploy --target prod2-main --app sub2api --repo-root /root/work/OP_Linux/.worktrees/sub2api-formal-surface-phased --dry-run
```

Expected:

- `app object search` / `verify` / `app resource verify` 成功
- `deploy --dry-run` 不再生成 compat rollback step，也不回退到 `secrets/app-resources/...`

- [ ] **Step 4: 准备集成说明，不在这一步自行合分支**

```bash
cd /root/work/sub2api/.worktrees/codex/sub2api-phase1-formal-surface
git status --short

cd /root/work/OP_Linux/.worktrees/sub2api-formal-surface-phased
git status --short
```

Expected:

- 两个 worktree 都是干净状态
- `sub2api` 与 `OP_Linux` 各自保留三阶段提交历史，便于独立 review 与合并
