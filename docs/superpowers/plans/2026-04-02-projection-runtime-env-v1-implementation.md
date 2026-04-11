# Projection Runtime Env V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans`. Keep checklist formatting for visibility.

**Goal:** 把 app runtime env projection 的正式路径放到 `uv run python -m ops.cli projection runtime-env <plan|apply|verify>`，不再通过 `tenant` surface 替代。所有测试、docs、skills、helpers、ENVs 都只使用 `projection runtime-env` naming。

**Architecture:** 新增 `ops.cli.projection`、`ops/domain/projection/runtime_env.py`，`handle_projection_command()` 汇总 `plan/apply/verify`，`projection runtime-env` 依赖 `inventory/servers/<target>/inventory.json` + `secrets/services/<app>.*.env` 以及 `projection/runtime-env` helper 输出的 `managed_keys`， `tests/test_projection_runtime_env_cli.py` 与 skill `.codex/skills/projection-ops/SKILL.md` 仅提 `projection runtime-env`。

**Tech Stack:** Python 3.12、`argparse`、`pytest`、env merge helpers、existing `ops.scripts.onepanel` tooling.

---

### Task 1: Stop exposing `render-env` from tenant

**Files:** `tests/test_cli_entrypoints.py`, `tests/test_projection_runtime_env_cli.py`

- [ ] **Step 1:** `tests/test_cli_entrypoints.py` 断言 `tenant` help 不包含 `render-env`，`projection --help`/`projection runtime-env --help` 正确列出 `plan|apply|verify`。
- [ ] **Step 2:** `tests/test_projection_runtime_env_cli.py` 写 `plan`/`apply`/`verify` contract，payload 包含 `projection.runtime_env.*` action，`error.id` 与 `drift` 等字段都在 `projection.runtime_env_*` 体系。
- [ ] **Step 3:** 初次运行 `uv run python -m pytest tests/test_cli_entrypoints.py tests/test_projection_runtime_env_cli.py -q`，确保 fail 因 CLI surface 未实现。

### Task 2: Build runtime env helpers

**Files:** `ops/domain/projection/runtime_env.py`, `tests/test_projection_runtime_env_cli.py`, `ops/cli/app_resource_state.py`

- [ ] **Step 1:** 封装 `build_runtime_env_projection(repo_root, target, app)`，返回 `{"action": "runtime-env.plan|apply|verify", "managed_keys": [...], "env_file": ..., "rendered_env": ...}`。
- [ ] **Step 2:** `runtime_env.py` 提供 `plan_runtime_env_projection`、`apply_runtime_env_projection`、`verify_runtime_env_projection`，`verify` 生成 `projection.runtime_env_drift` / `projection.runtime_env_missing` 错误码跟 `managed_keys` / `drift_keys` 结构。
- [ ] **Step 3:** `tests/test_projection_runtime_env_cli.py` 校验 helper 输出与 `plan/apply/verify` payload。

### Task 3: Publish the projection CLI surface

**Files:** `ops/cli/projection.py`, `ops/cli/app.py`, `tests/test_projection_runtime_env_cli.py`, `tests/test_cli_entrypoints.py`

- [ ] **Step 1:** `ops/cli/projection.py` 新建 parser：`projection runtime-env plan|apply|verify` ，每个动作都有 `--target`, `--app`, `--repo-root`，`apply` 额外支持 `--write`。
- [ ] **Step 2:** `handle_projection_command()` 从 `runtime_env.py` 调用 `plan/apply/verify`，通过 `_wrap_projection()` 返回 `command="projection"`、`action="runtime-env.plan|apply|verify"`。
- [ ] **Step 3:** 在 `ops/cli/app.py` 注册 `projection` parser、`handle_projection_command()`，`main()` dispatch `projection` 结果，`run_cli("--help")` 需展示 `projection` entry。
- [ ] **Step 4:** `tests/test_projection_runtime_env_cli.py` 验证 `projection runtime-env apply` 仍编排 helper 输出，并确保 `tenant render-env` 相关逻辑从 CLI 流程去除。

### Task 4: Docs, skills, & catalog

**Files:** `README.md`, `docs/architecture/control-plane.md`, `.codex/skills/projection-ops/SKILL.md`, `.codex/skills/catalog.yaml`, `tests/test_onepanel_plugin_and_skills.py`

- [ ] **Step 1:** README/control-plane/runbooks 里新增 `projection runtime-env plan/apply/verify` 语句，说明 `projection` surface 负责 app runtime env projection。
- [ ] **Step 2:** `.codex/skills/projection-ops/SKILL.md` 列出正式命令，`catalog.yaml` 以 `entrypoint: uv run python -m ops.cli projection` 定义，并让 `tests/test_onepanel_plugin_and_skills.py` 验证 skill 文本中有 `projection runtime-env`。
- [ ] **Step 3:** `tests/test_docs_no_legacy_terms.py` 黑名单中不再包括 `render-env`，active docs 只有 `projection runtime-env` 相关表述。

### Task 5: Final verification

**Files:** verify only

- [ ] **Step 1:** `uv run python -m pytest tests/test_projection_runtime_env_cli.py tests/test_cli_entrypoints.py tests/test_onepanel_plugin_and_skills.py -q`
- [ ] **Step 2:** `uv run python -m ops.cli projection runtime-env --help` 显示 three actions，顶层 CLI help 不再提已移除的旧 runtime-env 入口。
- [ ] **Step 3:** `rg -n \"render-env\" docs/ README.md .codex/skills` 只有历史计划匹配。
