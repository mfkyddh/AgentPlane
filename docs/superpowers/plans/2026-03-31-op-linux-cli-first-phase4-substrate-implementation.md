# OP_Linux CLI-First Phase 4 Substrate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在不进入应用层运行面改造、也不新增 `host / service / website` 公开 CLI 骨架的前提下，完成 Phase 4 的 remote substrate、remote 目录语义和 onepanel compat helper 边界收口。

**Architecture:** 这次实现只做“正式链路收口 + compat 资产降级 + internal 承接面显式化”。正式 `ops.cli` 先统一回到 Python remote substrate；`ops/scripts/remote/` 保留 transport/compat 最小表面；`ops/scripts/onepanel/` 保留 internal object layer，并把历史脚本入口明确压回 compat。

**Tech Stack:** Python 3, `uv`, `pytest`, Bash thin wrapper, Markdown runbooks, Git worktree.

---

## File Map

### 正式执行链

- [ops/cli/remote.py](/root/work/OP_Linux/.worktrees/codex-cli-first-repo-refactor/ops/cli/remote.py)
  - 继续承载 `remote bash` CLI，同时抽出仓库内部可复用的 Python remote executor。
- [ops/cli/prod0_postgres_app_resource_audit.py](/root/work/OP_Linux/.worktrees/codex-cli-first-repo-refactor/ops/cli/prod0_postgres_app_resource_audit.py)
  - 把 `audit-live` 改成直接复用 Python remote substrate。

### remote 目录语义

- [ops/scripts/remote/run_remote_bash.sh](/root/work/OP_Linux/.worktrees/codex-cli-first-repo-refactor/ops/scripts/remote/run_remote_bash.sh)
  - 保留 compat passthrough。
- [ops/scripts/remote/prod0-postgres-app-resource-live-audit.sh](/root/work/OP_Linux/.worktrees/codex-cli-first-repo-refactor/ops/scripts/remote/prod0-postgres-app-resource-live-audit.sh)
  - 继续被正式命令复用，但明确为 internal remote helper。
- [ops/scripts/internal/remote/](/root/work/OP_Linux/.worktrees/codex-cli-first-repo-refactor/ops/scripts/internal/remote)
  - 新增 internal remote 承接目录。
- [ops/scripts/internal/remote/example.sh](/root/work/OP_Linux/.worktrees/codex-cli-first-repo-refactor/ops/scripts/internal/remote/example.sh)
  - 从 `ops/scripts/remote/` 迁入。
- [ops/scripts/internal/remote/example-arg.sh](/root/work/OP_Linux/.worktrees/codex-cli-first-repo-refactor/ops/scripts/internal/remote/example-arg.sh)
  - 从 `ops/scripts/remote/` 迁入。

### onepanel compat 边界

- [ops/cli/apps.py](/root/work/OP_Linux/.worktrees/codex-cli-first-repo-refactor/ops/cli/apps.py)
  - 显式标记对历史 onepanel 脚本入口的 compat 依赖。
- [ops/scripts/onepanel/api_request.py](/root/work/OP_Linux/.worktrees/codex-cli-first-repo-refactor/ops/scripts/onepanel/api_request.py)
  - 标明 compat entrypoint。
- [ops/scripts/onepanel/app_lifecycle.py](/root/work/OP_Linux/.worktrees/codex-cli-first-repo-refactor/ops/scripts/onepanel/app_lifecycle.py)
  - 标明 compat entrypoint。
- [ops/scripts/onepanel/project_lifecycle.py](/root/work/OP_Linux/.worktrees/codex-cli-first-repo-refactor/ops/scripts/onepanel/project_lifecycle.py)
  - 标明 compat entrypoint。
- [ops/scripts/onepanel/env_targets.py](/root/work/OP_Linux/.worktrees/codex-cli-first-repo-refactor/ops/scripts/onepanel/env_targets.py)
  - 保留绝对路径与 legacy fallback 合同，但明确标成 compat contract。

### 文档与合同测试

- [docs/runbooks/powershell-wsl-remote-bash.md](/root/work/OP_Linux/.worktrees/codex-cli-first-repo-refactor/docs/runbooks/powershell-wsl-remote-bash.md)
- [docs/runbooks/control-plane-legacy-migration.md](/root/work/OP_Linux/.worktrees/codex-cli-first-repo-refactor/docs/runbooks/control-plane-legacy-migration.md)
- [tests/test_remote_cli.py](/root/work/OP_Linux/.worktrees/codex-cli-first-repo-refactor/tests/test_remote_cli.py)
- [tests/test_prod0_postgres_app_resource_audit.py](/root/work/OP_Linux/.worktrees/codex-cli-first-repo-refactor/tests/test_prod0_postgres_app_resource_audit.py)
- [tests/test_repo_snapshot_contracts.py](/root/work/OP_Linux/.worktrees/codex-cli-first-repo-refactor/tests/test_repo_snapshot_contracts.py)
- [tests/test_wsl_first_docs.py](/root/work/OP_Linux/.worktrees/codex-cli-first-repo-refactor/tests/test_wsl_first_docs.py)
- [docs/superpowers/plans/2026-03-31-op-linux-cli-first-repo-refactor.md](/root/work/OP_Linux/.worktrees/codex-cli-first-repo-refactor/docs/superpowers/plans/2026-03-31-op-linux-cli-first-repo-refactor.md)

## Task 1: 抽出可复用的 Python Remote Substrate

**Files:**
- Modify: `ops/cli/remote.py`
- Test: `tests/test_remote_cli.py`

- [ ] **Step 1: 在 `tests/test_remote_cli.py` 先写 substrate 级失败测试**

```python
import unittest
from unittest import mock

from ops.cli import remote as remote_cli


class RemoteCliTests(unittest.TestCase):
    def test_execute_remote_bash_accepts_explicit_stdin_text(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            inventory_file = root / "inventory" / "servers" / "prod0-main" / "inventory.json"
            inventory_file.parent.mkdir(parents=True, exist_ok=True)
            inventory_file.write_text(
                json.dumps({"ssh": {"aliases": ["prod0-main"], "user": "root"}}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

            completed = subprocess.CompletedProcess(
                args=[],
                returncode=0,
                stdout="remote ok\n",
                stderr="",
            )

            with mock.patch.object(remote_cli, "next_operation_id", return_value="remote-bash-test"), \
                mock.patch.object(remote_cli, "append_operation_ledger", return_value={"ledger_file": str(root / "ledger.jsonl")}), \
                mock.patch.object(remote_cli.subprocess, "run", return_value=completed) as run:
                payload = remote_cli.execute_remote_bash(
                    repo_root=root,
                    target="prod0-main",
                    remote_args=["echo", "ok"],
                    stdin_text="echo remote_ok\n",
                )

        self.assertTrue(payload["ok"])
        self.assertEqual("stdin", payload["transport"])
        self.assertEqual("remote ok\n", payload["result"]["stdout"])
        run.assert_called_once()
        self.assertEqual("echo remote_ok\n", run.call_args.kwargs["input"])
```

- [ ] **Step 2: 跑单测，确认当前实现没有该内部 API**

Run:

```bash
cd /root/work/OP_Linux/.worktrees/codex-cli-first-repo-refactor
uv run python -m pytest tests/test_remote_cli.py -q
```

Expected:
- 失败，报 `AttributeError: module 'ops.cli.remote' has no attribute 'execute_remote_bash'`

- [ ] **Step 3: 在 `ops/cli/remote.py` 实现可复用 executor，并让 CLI handler 复用它**

```python
def _execute_remote_bash(
    command: list[str],
    *,
    script_file: Path | None,
    stdin_text: str | None = None,
) -> subprocess.CompletedProcess[str]:
    if script_file is not None:
        with script_file.open("r", encoding="utf-8") as handle:
            return subprocess.run(command, stdin=handle, text=True, capture_output=True, check=False)

    if stdin_text is None:
        stdin_text = sys.stdin.read()
    if not stdin_text:
        raise ValueError("stdin is empty; pass --script-file <linux-path> or provide stdin_text")
    return subprocess.run(command, input=stdin_text, text=True, capture_output=True, check=False)


def execute_remote_bash(
    *,
    repo_root: Path,
    target: str,
    remote_args: list[str] | None = None,
    script_file: Path | None = None,
    stdin_text: str | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    normalized_args = _strip_remainder_separator(list(remote_args or []))
    ssh_target = resolve_ssh_target(repo_root, target)
    op_id = next_operation_id("remote-bash")
    transport = "script-file" if script_file is not None else "stdin"
    payload = _render_payload(
        repo_root=repo_root,
        target=target,
        ssh_target=ssh_target,
        remote_args=normalized_args,
        transport=transport,
        script_file=script_file,
        dry_run=dry_run,
    )
    if dry_run:
        _record_operation(repo_root, target=target, payload=payload, op_id=op_id, result="planned")
        return payload

    result = _execute_remote_bash(payload["ssh_argv"], script_file=script_file, stdin_text=stdin_text)
    payload["ok"] = result.returncode == 0
    payload["result"] = {
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }
    _record_operation(
        repo_root,
        target=target,
        payload=payload,
        op_id=op_id,
        result="succeeded" if result.returncode == 0 else "failed",
    )
    return payload


def handle_remote_command(args: argparse.Namespace) -> dict[str, Any]:
    ...
    return execute_remote_bash(
        repo_root=repo_root,
        target=args.target,
        remote_args=remote_args,
        script_file=script_file,
        dry_run=args.dry_run,
    )
```

- [ ] **Step 4: 跑 remote 相关测试，确认 CLI 行为与新 substrate 一致**

Run:

```bash
cd /root/work/OP_Linux/.worktrees/codex-cli-first-repo-refactor
uv run python -m pytest tests/test_remote_cli.py tests/test_cli_entrypoints.py -q
```

Expected:
- 全部通过
- 原有 `remote bash --dry-run` 结构化输出保持不变

- [ ] **Step 5: 提交 Task 1**

```bash
cd /root/work/OP_Linux/.worktrees/codex-cli-first-repo-refactor
git add tests/test_remote_cli.py ops/cli/remote.py
git commit -m "refactor: extract reusable remote substrate"
```

## Task 2: 把 Tenant Live Audit 切到 Python Remote Substrate

**Files:**
- Modify: `ops/cli/prod0_postgres_app_resource_audit.py`
- Test: `tests/test_prod0_postgres_app_resource_audit.py`

- [ ] **Step 1: 在 `tests/test_prod0_postgres_app_resource_audit.py` 增加直接断言 substrate 调用的失败测试**

```python
from ops.cli import tenant as tenant_cli


class TenantCliTests(unittest.TestCase):
    def test_prod0_live_audit_snapshot_uses_python_remote_substrate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            snapshot_payload = {
                "apps": {"sub2apipay": {"database": "sub2apipay", "user": "sub2apipay_prod0"}},
                "catalog": {"databases": {"sub2apipay": "sub2apipay_prod0"}},
            }

            with mock.patch(
                "ops.cli.tenant.execute_remote_bash",
                return_value={
                    "ok": True,
                    "result": {
                        "returncode": 0,
                        "stdout": json.dumps(snapshot_payload),
                        "stderr": "",
                    },
                },
            ) as execute:
                snapshot = tenant_cli._prod0_live_audit_snapshot(root)

        self.assertEqual(snapshot_payload, snapshot)
        self.assertEqual(root, execute.call_args.kwargs["repo_root"])
        self.assertEqual("prod0-main", execute.call_args.kwargs["target"])
        self.assertTrue(str(execute.call_args.kwargs["script_file"]).endswith("prod0-postgres-app-resource-live-audit.sh"))
```

- [ ] **Step 2: 跑单测，确认 `tenant.py` 仍然直接 `subprocess.run`**

Run:

```bash
cd /root/work/OP_Linux/.worktrees/codex-cli-first-repo-refactor
uv run python -m pytest tests/test_prod0_postgres_app_resource_audit.py -q
```

Expected:
- 新增测试失败，报 `AttributeError` 或 mock 未被调用

- [ ] **Step 3: 在 `ops/cli/prod0_postgres_app_resource_audit.py` 改用 `execute_remote_bash()`，不再回跳 `run_remote_bash.sh`**

```python
from ops.cli.remote import execute_remote_bash


def _prod0_live_audit_snapshot(repo_root: Path) -> dict[str, Any]:
    audit_script = repo_root / "ops" / "scripts" / "remote" / "prod0-postgres-app-resource-live-audit.sh"
    payload = execute_remote_bash(
        repo_root=repo_root,
        target="prod0-main",
        script_file=audit_script,
    )
    result = payload.get("result", {})
    returncode = int(result.get("returncode", 1))
    stdout = str(result.get("stdout", ""))
    stderr = str(result.get("stderr", ""))
    if returncode != 0:
        message = stderr.strip() or stdout.strip() or f"prod0 live audit failed with exit code {returncode}"
        raise RuntimeError(message)
    parsed = json.loads(stdout)
    if not isinstance(parsed, dict):
        raise ValueError("prod0 live audit stdout must be a JSON object")
    return parsed
```

- [ ] **Step 4: 跑 tenant 与 remote 联合测试**

Run:

```bash
cd /root/work/OP_Linux/.worktrees/codex-cli-first-repo-refactor
uv run python -m pytest tests/test_prod0_postgres_app_resource_audit.py tests/test_remote_cli.py -q
```

Expected:
- 全部通过
- `tenant audit-live` 的行为不变，但正式链路不再依赖 shell compat wrapper

- [ ] **Step 5: 提交 Task 2**

```bash
cd /root/work/OP_Linux/.worktrees/codex-cli-first-repo-refactor
git add ops/cli/prod0_postgres_app_resource_audit.py tests/test_prod0_postgres_app_resource_audit.py
git commit -m "refactor: route tenant live audit through remote substrate"
```

## Task 3: 收紧 `ops/scripts/remote/` 目录语义

**Files:**
- Modify: `ops/scripts/remote/run_remote_bash.sh`
- Modify: `ops/scripts/remote/prod0-postgres-app-resource-live-audit.sh`
- Create: `ops/scripts/internal/remote/README.md`
- Move: `ops/scripts/remote/example.sh`
- Move: `ops/scripts/remote/example-arg.sh`
- Modify: `tests/test_repo_snapshot_contracts.py`

- [ ] **Step 1: 在 `tests/test_repo_snapshot_contracts.py` 先冻结新旧 remote 路径合同**

```python
class RepoSnapshotContractsTests(unittest.TestCase):
    def test_remote_examples_live_under_internal_remote(self) -> None:
        self.assertTrue((REPO_ROOT / "ops/scripts/internal/remote/example.sh").is_file())
        self.assertTrue((REPO_ROOT / "ops/scripts/internal/remote/example-arg.sh").is_file())
        self.assertFalse((REPO_ROOT / "ops/scripts/remote/example.sh").exists())
        self.assertFalse((REPO_ROOT / "ops/scripts/remote/example-arg.sh").exists())

    def test_remote_transport_wrapper_still_exists(self) -> None:
        wrapper = REPO_ROOT / "ops/scripts/remote/run_remote_bash.sh"
        self.assertTrue(wrapper.is_file(), f"missing remote compat wrapper: {wrapper}")
```

- [ ] **Step 2: 跑 snapshot 测试，确认新路径还不存在**

Run:

```bash
cd /root/work/OP_Linux/.worktrees/codex-cli-first-repo-refactor
uv run python -m pytest tests/test_repo_snapshot_contracts.py -q
```

Expected:
- 失败，报 `ops/scripts/internal/remote/example.sh` 不存在

- [ ] **Step 3: 创建 internal 目录、迁移示例脚本，并给 remote helper 加语义标记**

```bash
cd /root/work/OP_Linux/.worktrees/codex-cli-first-repo-refactor
mkdir -p ops/scripts/internal/remote
git mv ops/scripts/remote/example.sh ops/scripts/internal/remote/example.sh
git mv ops/scripts/remote/example-arg.sh ops/scripts/internal/remote/example-arg.sh
```

```markdown
# Internal Remote Helpers

本目录承接仍被正式 CLI 复用、但暂未对象化替代的 internal remote 资产。

- `example.sh` / `example-arg.sh` 只用于文档与测试 fixture。
- `ops/scripts/remote/` 只保留 transport / compat 入口，例如 `run_remote_bash.sh`。
- 高风险专题脚本继续按 internal helper 管理，不在本阶段重写运行语义。
```

```bash
#!/usr/bin/env bash
# Compatibility shim only. Prefer: uv run python -m ops.cli remote bash ...
```

```bash
#!/usr/bin/env bash
# Internal remote helper used by `ops.cli tenant audit-live`.
```

- [ ] **Step 4: 跑 snapshot 与 remote 相关测试**

Run:

```bash
cd /root/work/OP_Linux/.worktrees/codex-cli-first-repo-refactor
uv run python -m pytest tests/test_repo_snapshot_contracts.py tests/test_remote_cli.py -q
```

Expected:
- 全部通过
- `ops/scripts/remote/` 目录里不再保留示例脚本

- [ ] **Step 5: 提交 Task 3**

```bash
cd /root/work/OP_Linux/.worktrees/codex-cli-first-repo-refactor
git add ops/scripts/remote/run_remote_bash.sh \
        ops/scripts/remote/prod0-postgres-app-resource-live-audit.sh \
        ops/scripts/internal/remote/README.md \
        ops/scripts/internal/remote/example.sh \
        ops/scripts/internal/remote/example-arg.sh \
        tests/test_repo_snapshot_contracts.py
git commit -m "refactor: tighten remote script directory semantics"
```

## Task 4: 明确 OnePanel Compat Helper 边界并同步文档

**Files:**
- Modify: `ops/cli/apps.py`
- Modify: `ops/scripts/onepanel/api_request.py`
- Modify: `ops/scripts/onepanel/app_lifecycle.py`
- Modify: `ops/scripts/onepanel/project_lifecycle.py`
- Modify: `ops/scripts/onepanel/env_targets.py`
- Modify: `docs/runbooks/powershell-wsl-remote-bash.md`
- Modify: `docs/runbooks/control-plane-legacy-migration.md`
- Modify: `tests/test_wsl_first_docs.py`

- [ ] **Step 1: 在 `tests/test_wsl_first_docs.py` 先写文档合同测试**

```python
class WslFirstDocsTests(unittest.TestCase):
    def test_phase4_runbooks_mark_remote_wrapper_as_compat_only(self) -> None:
        text = (REPO_ROOT / "docs" / "runbooks" / "powershell-wsl-remote-bash.md").read_text(encoding="utf-8")
        self.assertIn("兼容层", text)
        self.assertIn("不再作为长期主命令面", text)

    def test_legacy_migration_runbook_marks_script_entrypoints_as_compat(self) -> None:
        text = (REPO_ROOT / "docs" / "runbooks" / "control-plane-legacy-migration.md").read_text(encoding="utf-8")
        self.assertIn("compat", text)
        self.assertIn("ops/scripts/remote/run_remote_bash.sh", text)
```

- [ ] **Step 2: 跑文档测试，确认术语还没完全冻结**

Run:

```bash
cd /root/work/OP_Linux/.worktrees/codex-cli-first-repo-refactor
uv run python -m pytest tests/test_wsl_first_docs.py -q
```

Expected:
- 失败，新增断言至少有一个不满足

- [ ] **Step 3: 给 onepanel 历史脚本入口补 compat 声明，并在 `apps.py` 标明这是过渡依赖**

```python
"""Compatibility entrypoint for signed 1Panel API requests.

Prefer `python -m ops.cli onepanel ...` for formal control-plane flows.
This file remains for remote path compatibility and targeted recovery.
"""
```

```python
"""Compatibility entrypoint for historical 1Panel app lifecycle flows.

Formal OP_Linux runbooks should route through `uv run python -m ops.cli ...`.
"""
```

```python
"""Compatibility entrypoint for historical 1Panel compose project flows."""
```

```python
# Compatibility contract: production targets still probe the historical
# `api_request.py` path, including `/opt/env_ubuntu/...`, until the remote
# estate no longer depends on that location.
def _remote_api_path_candidates(...):
    ...
```

```python
def _onepanel_lifecycle_step(repo_root: Path, *, target: str, operate: str, rollback_entry: dict[str, Any]) -> tuple[list[str], str]:
    # Compatibility bridge: rollback still shells through the historical
    # onepanel lifecycle helper until object_api-backed lifecycle steps replace it.
    script_path = repo_root / "ops" / "scripts" / "onepanel" / "app_lifecycle.py"
    ...
```

```markdown
- `ops/scripts/remote/run_remote_bash.sh` 只保留兼容层语义，不再作为长期主命令面。
- `ops/scripts/onepanel/api_request.py` 与 `app_lifecycle.py` 属于 compat helper。
```

- [ ] **Step 4: 跑文档与 onepanel 过渡合同测试**

Run:

```bash
cd /root/work/OP_Linux/.worktrees/codex-cli-first-repo-refactor
uv run python -m pytest tests/test_wsl_first_docs.py tests/test_onepanel_env_targets.py tests/test_onepanel_plugin_and_skills.py -q
```

Expected:
- 全部通过
- runbook 明确写出 compat 语义
- onepanel 远端绝对路径与 legacy fallback 合同保持不变

- [ ] **Step 5: 提交 Task 4**

```bash
cd /root/work/OP_Linux/.worktrees/codex-cli-first-repo-refactor
git add ops/cli/apps.py \
        ops/scripts/onepanel/api_request.py \
        ops/scripts/onepanel/app_lifecycle.py \
        ops/scripts/onepanel/project_lifecycle.py \
        ops/scripts/onepanel/env_targets.py \
        docs/runbooks/powershell-wsl-remote-bash.md \
        docs/runbooks/control-plane-legacy-migration.md \
        tests/test_wsl_first_docs.py
git commit -m "docs: mark onepanel and remote helpers as compat"
```

## Task 5: 跑 Phase 4 验证并回写阶段状态

**Files:**
- Modify: `docs/superpowers/plans/2026-03-31-op-linux-cli-first-repo-refactor.md`

- [ ] **Step 1: 先跑 Phase 4 最小验证集**

Run:

```bash
cd /root/work/OP_Linux/.worktrees/codex-cli-first-repo-refactor
uv run python -m pytest tests/test_cli_entrypoints.py tests/test_wsl_first_docs.py -q
uv run python -m pytest tests/test_onepanel_env_targets.py tests/test_onepanel_plugin_and_skills.py -q
uv run python -m pytest tests/test_remote_cli.py tests/test_prod0_postgres_app_resource_audit.py tests/test_repo_snapshot_contracts.py tests/test_app_cli.py -q
```

Expected:
- 全部通过
- 不需要额外进入应用层测试

- [ ] **Step 2: 在总计划文件里回写 Phase 4 状态**

```markdown
- [x] Phase 4: 收敛 remote 层与 transport substrate
```

```markdown
- [x] **Step 1: 统一 Python remote executor 调用链**
- [x] **Step 2: 重定义 `ops/scripts/remote/` 目录语义**
- [x] **Step 3: 先吸收已有正式语义的脚本**
- [x] **Step 4: 标记但不越界处理高风险专题脚本**
- [x] **Step 5: 收敛 onepanel helper 的定位，不直接删除**
- [x] **Step 6: 跑阶段验证**
- [x] **Step 7: 更新状态并写 Phase 4 总结**
```

- [ ] **Step 3: 填写 `Phase 4 Summary`**

```markdown
### Phase 4 Summary

- [x] 已填写
- 已完成的工作：`ops.cli remote` 已提供仓库内部可复用的 Python substrate，`tenant audit-live` 已直接复用该 substrate；`ops/scripts/remote/` 已压回 transport/compat/internal 语义，示例脚本迁入 `ops/scripts/internal/remote/`；`ops/scripts/onepanel/` 的历史脚本入口已明确标为 compat helper，runbook 与 legacy migration 文档已同步改口。
- 这些工作如何对应总体目标：正式命令面不再回跳 shell wrapper，第二控制面的执行语义被压回 compat 层；同时 future `host / service / website` 已有统一的 remote substrate 和 onepanel internal 承接面可复用。
- 还没解决什么：`host / service / website` 公开对象层尚未建立；高风险专题脚本仍处在 internal/compat 过渡态；onepanel helper 仍未完成对象化替代。
- 下一阶段从哪里开始：从 Phase 5 开始，继续收敛 skills / plugins / pointer 层，把 canonical metadata 与派生层关系压薄。
```

- [ ] **Step 4: 提交 Task 5**

```bash
cd /root/work/OP_Linux/.worktrees/codex-cli-first-repo-refactor
git add docs/superpowers/plans/2026-03-31-op-linux-cli-first-repo-refactor.md
git commit -m "docs: close phase4 substrate refactor"
```

## Self-Review

### Spec Coverage

- `remote substrate`：Task 1、Task 2
- `remote 目录语义`：Task 3
- `onepanel compat helper`：Task 4
- `文档与测试口径`：Task 4、Task 5
- `Phase 4 状态回写`：Task 5

没有遗漏 `spec` 中的正式链路收口、compat 降级、internal 承接面显式化这三类要求。

### Placeholder Scan

- 没有使用占位词或“以后再补”的描述
- 每个任务都给了精确文件路径、命令和预期结果
- 代码步骤都给了明确片段，而不是“自行处理错误”之类空话

### Type Consistency

- remote 内部 API 统一命名为 `execute_remote_bash`
- tenant 继续消费 `dict[str, Any]` 结构化 payload
- onepanel 历史脚本入口统一称为 `compat helper`，未混入“正式入口”措辞

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-03-31-op-linux-cli-first-phase4-substrate-implementation.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**
