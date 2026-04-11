# Host Object CLI-First Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 `OP_Linux` 新增第一版显式 `host` 对象域，把宿主机基础治理的正式入口收口到 `uv run python -m ops.cli host ...`，同时保留旧入口作为 compat 路径。

**Architecture:** 新增 `ops/cli/host.py` 作为薄桥接层，只统一对象入口与顶层返回结构，不重写 `inventory`、`audit filesystem`、`remote bash`、`secrets sync-host-layout` 的现有实现。测试先冻结 `host` CLI 合同，再最小化接线；文档和 skill 随后切到 `host` 正式口径，并明确 `network / panel / firewall` 仍属于下一阶段桥接对象。

**Tech Stack:** Python 3、`argparse`、`pytest`、repo-local Markdown docs/skills、Git worktree

---

## File Map

- Create: `ops/cli/host.py`
- Create: `tests/test_host_cli.py`
- Modify: `ops/cli/app.py`
- Modify: `tests/test_cli_entrypoints.py`
- Modify: `tests/test_docs_no_legacy_terms.py`
- Modify: `AGENTS.md`
- Modify: `README.md`
- Modify: `docs/architecture/control-plane.md`
- Modify: `docs/runbooks/wsl-host-governance.md`
- Modify: `.codex/skills/host-ops/SKILL.md`

## Task 1: 冻结 `host` CLI 合同测试

**Files:**
- Create: `tests/test_host_cli.py`
- Modify: `tests/test_cli_entrypoints.py`

- [x] **Step 1: 写 `host` 顶层帮助与子命令的失败测试**

在 `tests/test_cli_entrypoints.py` 的顶层帮助检查里加入 `host`，并在 `tests/test_host_cli.py` 新建最小合同测试：

```python
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def run_cli(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "ops.cli", *args],
        cwd=cwd or REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


class HostCliTests(unittest.TestCase):
    def test_host_help_lists_inventory_audit_remote_and_secrets_layout(self) -> None:
        result = run_cli("host", "--help")
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertIn("inventory", result.stdout)
        self.assertIn("audit", result.stdout)
        self.assertIn("remote", result.stdout)
        self.assertIn("secrets-layout", result.stdout)
```

- [x] **Step 2: 运行测试确认它先失败**

Run:

```bash
cd /root/work/OP_Linux/.worktrees/codex-cli-first-repo-refactor
uv run python -m pytest tests/test_cli_entrypoints.py tests/test_host_cli.py -q
```

Expected:

- 失败点包含 `host` 子命令尚不存在

- [x] **Step 3: 写 `host inventory/audit/remote/secrets-layout` 的桥接合同失败测试**

在 `tests/test_host_cli.py` 继续补四个最小行为：

```python
    def test_host_inventory_wraps_inventory_payload(self) -> None:
        result = run_cli("host", "inventory", "wsl", "--repo-root", str(REPO_ROOT))
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual("host", payload["command"])
        self.assertEqual("inventory", payload["action"])
        self.assertEqual("wsl", payload["target"])
        self.assertEqual("inventory", payload["compat_source"])
        self.assertIsInstance(payload["payload"], dict)

    def test_host_audit_wraps_filesystem_audit_payload(self) -> None:
        result = run_cli("host", "audit", "wsl", "--repo-root", str(REPO_ROOT))
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual("host", payload["command"])
        self.assertEqual("audit", payload["action"])
        self.assertEqual("wsl", payload["target"])
        self.assertEqual("audit.filesystem", payload["compat_source"])
        self.assertIsInstance(payload["payload"], dict)

    def test_host_remote_bash_wraps_dry_run_payload(self) -> None:
        script = REPO_ROOT / "ops" / "scripts" / "internal" / "remote" / "example.sh"
        result = run_cli(
            "host",
            "remote",
            "bash",
            "prod0-main",
            "--repo-root",
            str(REPO_ROOT),
            "--dry-run",
            "--script-file",
            str(script),
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual("host", payload["command"])
        self.assertEqual("remote.bash", payload["action"])
        self.assertEqual("prod0-main", payload["target"])
        self.assertEqual("remote.bash", payload["compat_source"])
        self.assertTrue(payload["payload"]["dry_run"])

    def test_host_secrets_layout_wraps_sync_host_layout_payload(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            host_root = root / "secrets" / "hosts" / "prod0-main" / "onepanel"
            host_root.mkdir(parents=True, exist_ok=True)
            (host_root / "api.env").write_text("ONEPANEL_API_KEY=demo\n", encoding="utf-8")

            result = run_cli(
                "host",
                "secrets-layout",
                "prod0-main",
                "--repo-root",
                str(root),
            )
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual("host", payload["command"])
            self.assertEqual("secrets-layout", payload["action"])
            self.assertEqual("prod0-main", payload["target"])
            self.assertEqual("secrets.sync-host-layout", payload["compat_source"])
            self.assertEqual("planned", payload["payload"]["projections"][0]["status"])
```

- [x] **Step 4: 再跑定向测试，确认仍按预期失败**

Run:

```bash
cd /root/work/OP_Linux/.worktrees/codex-cli-first-repo-refactor
uv run python -m pytest tests/test_host_cli.py -q
```

Expected:

- 所有失败都来自 `host` 命令尚未接线，而不是测试拼写或 fixture 错误

## Task 2: 最小实现 `host` 桥接层

**Files:**
- Create: `ops/cli/host.py`
- Modify: `ops/cli/app.py`

- [x] **Step 1: 新建 `ops/cli/host.py`，只做 parser 与桥接函数**

新增最小桥接文件：

```python
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from ops.cli.audit import audit_filesystem
from ops.cli.inventory import generate_inventory_snapshot
from ops.cli.remote import execute_remote_bash
from ops.cli.secrets import SUPPORTED_SECRET_TARGETS, materialize_legacy_host_layout


SUPPORTED_HOST_TARGETS = SUPPORTED_SECRET_TARGETS


def add_host_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    host_parser = subparsers.add_parser("host", help="主机基线与主机级治理")
    host_subparsers = host_parser.add_subparsers(dest="host_action", required=True)

    inventory = host_subparsers.add_parser("inventory", help="生成主机结构化清单")
    inventory.add_argument("target", choices=SUPPORTED_HOST_TARGETS)
    inventory.add_argument("--repo-root", default=".")
    inventory.add_argument("--write", action="store_true")

    audit = host_subparsers.add_parser("audit", help="执行主机基线审计")
    audit.add_argument("target", choices=SUPPORTED_HOST_TARGETS)
    audit.add_argument("--repo-root", default=".")

    remote = host_subparsers.add_parser("remote", help="主机远端执行入口")
    remote_subparsers = remote.add_subparsers(dest="host_remote_action", required=True)
    bash_parser = remote_subparsers.add_parser("bash", help="通过 ssh -T 执行远端 bash")
    bash_parser.add_argument("target", choices=SUPPORTED_HOST_TARGETS)
    bash_parser.add_argument("--repo-root", default=".")
    bash_parser.add_argument("--script-file")
    bash_parser.add_argument("--dry-run", action="store_true")
    bash_parser.add_argument("remote_args", nargs="*")

    secrets_layout = host_subparsers.add_parser("secrets-layout", help="同步 host-first secrets 布局")
    secrets_layout.add_argument("target", choices=SUPPORTED_HOST_TARGETS)
    secrets_layout.add_argument("--repo-root", default=".")
    secrets_layout.add_argument("--write", action="store_true")


def _wrap(*, action: str, target: str, compat_source: str, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "command": "host",
        "action": action,
        "target": target,
        "compat_source": compat_source,
        "payload": payload,
    }


def handle_host_command(args: argparse.Namespace) -> dict[str, Any]:
    repo_root = Path(getattr(args, "repo_root", ".")).resolve()
    if args.host_action == "inventory":
        return _wrap(
            action="inventory",
            target=args.target,
            compat_source="inventory",
            payload=generate_inventory_snapshot(repo_root, args.target, write=bool(args.write)),
        )
    if args.host_action == "audit":
        return _wrap(
            action="audit",
            target=args.target,
            compat_source="audit.filesystem",
            payload=audit_filesystem(repo_root, args.target),
        )
    if args.host_action == "remote" and args.host_remote_action == "bash":
        return _wrap(
            action="remote.bash",
            target=args.target,
            compat_source="remote.bash",
            payload=execute_remote_bash(
                repo_root=repo_root,
                target=args.target,
                remote_args=list(args.remote_args),
                script_file=args.script_file,
                dry_run=bool(args.dry_run),
            ),
        )
    if args.host_action == "secrets-layout":
        return _wrap(
            action="secrets-layout",
            target=args.target,
            compat_source="secrets.sync-host-layout",
            payload=materialize_legacy_host_layout(repo_root, args.target, write=bool(args.write)),
        )
    raise ValueError(f"Unsupported host action: {args.host_action}")
```

- [x] **Step 2: 在 `ops/cli/app.py` 接入 `host` parser 与 handler**

最小改动：

```python
from ops.cli.host import add_host_parser, handle_host_command
```

并在 `build_parser()` 中注册：

```python
    add_host_parser(subparsers)
```

并在 `main()` 中新增：

```python
    if args.command == "host":
        try:
            _emit(handle_host_command(args))
            return 0
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 1
```

- [x] **Step 3: 跑 `host` 定向测试，确认转绿**

Run:

```bash
cd /root/work/OP_Linux/.worktrees/codex-cli-first-repo-refactor
uv run python -m pytest tests/test_cli_entrypoints.py tests/test_host_cli.py tests/test_secrets_host_layout.py -q
```

Expected:

- `host` 相关合同测试通过
- 旧 `secrets` host layout 测试继续通过

- [x] **Step 4: 做一次最小重构，不改行为**

如果需要，只允许做两类清理：

- 抽 `_wrap(...)`
- 保持 `SUPPORTED_HOST_TARGETS` 与 `SUPPORTED_SECRET_TARGETS` 同步

不允许在这一阶段扩展 `network`、`panel`、`firewall`

- [x] **Step 5: 再跑定向测试确认保持全绿**

Run:

```bash
cd /root/work/OP_Linux/.worktrees/codex-cli-first-repo-refactor
uv run python -m pytest tests/test_cli_entrypoints.py tests/test_host_cli.py tests/test_secrets_host_layout.py -q
```

Expected:

- `host` CLI 合同仍通过

## Task 3: 切换文档与 skill 到 `host` 正式口径

**Files:**
- Modify: `README.md`
- Modify: `docs/architecture/control-plane.md`
- Modify: `docs/runbooks/wsl-host-governance.md`
- Modify: `.codex/skills/host-ops/SKILL.md`
- Modify: `tests/test_docs_no_legacy_terms.py`
- Modify: `AGENTS.md`

- [x] **Step 1: 先补文档合同失败测试**

在 `tests/test_docs_no_legacy_terms.py` 增加对 `host` 正式入口的断言，例如：

```python
        self.assertIn("uv run python -m ops.cli host inventory wsl", readme_text)
        self.assertIn("uv run python -m ops.cli host audit wsl", readme_text)
```

对 WSL runbook 和 host skill 增加类似断言：

```python
        wsl_host_text = (REPO_ROOT / "docs" / "runbooks" / "wsl-host-governance.md").read_text(encoding="utf-8")
        host_skill_text = (REPO_ROOT / ".codex" / "skills" / "host-ops" / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("uv run python -m ops.cli host inventory wsl", wsl_host_text)
        self.assertIn("uv run python -m ops.cli host remote bash prod0-main", wsl_host_text)
        self.assertIn("uv run python -m ops.cli host inventory <target>", host_skill_text)
```

- [x] **Step 2: 运行文档测试确认先失败**

Run:

```bash
cd /root/work/OP_Linux/.worktrees/codex-cli-first-repo-refactor
uv run python -m pytest tests/test_docs_no_legacy_terms.py -q
```

Expected:

- 失败点来自文档尚未切到 `host` 正式口径

- [x] **Step 3: 最小化改文档与 skill**

最小调整方向：

```md
- 生产清单：`uv run python -m ops.cli inventory prod0-main`
- 常用主机入口：`uv run python -m ops.cli host inventory prod0-main`
- 常用主机审计：`uv run python -m ops.cli host audit wsl`
```

`docs/architecture/control-plane.md` 增补第一版 `host` 对象面：

```md
- `host` 第一版正式入口：`inventory`、`audit`、`remote.bash`、`secrets-layout`
- `network`、`onepanel panel`、`onepanel firewall` 仍保留原域，属于下一阶段桥接对象
```

`docs/runbooks/wsl-host-governance.md` 把示例入口切到：

```bash
env -C /root/work/OP_Linux uv run python -m ops.cli host audit wsl --repo-root /root/work/OP_Linux
env -C /root/work/OP_Linux uv run python -m ops.cli host inventory wsl --repo-root /root/work/OP_Linux
env -C /root/work/OP_Linux uv run python -m ops.cli host remote bash prod0-main --dry-run --script-file /root/work/OP_Linux/ops/scripts/internal/remote/example.sh
env -C /root/work/OP_Linux uv run python -m ops.cli host secrets-layout wsl --repo-root /root/work/OP_Linux
```

`.codex/skills/host-ops/SKILL.md` 切到：

```bash
uv run python -m ops.cli host inventory <target> --repo-root /root/work/OP_Linux
uv run python -m ops.cli host remote bash <target> -- whoami
uv run python -m ops.cli host secrets-layout <target> --repo-root /root/work/OP_Linux --write
```

- [x] **Step 4: 跑文档与 `host` 组合验证**

Run:

```bash
cd /root/work/OP_Linux/.worktrees/codex-cli-first-repo-refactor
uv run python -m pytest tests/test_host_cli.py tests/test_docs_no_legacy_terms.py tests/test_wsl_first_docs.py -q
```

Expected:

- `host` CLI 合同测试通过
- 文档合同测试通过
- WSL-first 合同不回退

## Task 4: 全量最小回归与提交

**Files:**
- Modify: `docs/superpowers/plans/2026-04-01-host-object-cli-first-implementation.md`

- [x] **Step 1: 回写计划状态**

在本计划文件中把已完成步骤勾选，并补一段简短阶段总结，说明：

- 第一版 `host` 已纳入哪些动作
- 哪些旧入口仍保留 compat
- `network / panel / firewall` 为什么仍未并入

- [x] **Step 2: 跑全量最小回归**

Run:

```bash
cd /root/work/OP_Linux/.worktrees/codex-cli-first-repo-refactor
uv run python -m pytest tests/test_cli_entrypoints.py tests/test_host_cli.py tests/test_docs_no_legacy_terms.py tests/test_wsl_first_docs.py tests/test_secrets_host_layout.py tests/test_inventory_generation.py tests/test_onepanel_plugin_and_skills.py tests/test_onepanel_env_targets.py tests/test_secrets_host_layout.py -q
```

Expected:

- 所有测试通过

- [x] **Step 3: 提交实现**

```bash
cd /root/work/OP_Linux/.worktrees/codex-cli-first-repo-refactor
git add ops/cli/host.py ops/cli/app.py tests/test_host_cli.py tests/test_cli_entrypoints.py tests/test_docs_no_legacy_terms.py README.md docs/architecture/control-plane.md docs/runbooks/wsl-host-governance.md .codex/skills/host-ops/SKILL.md docs/superpowers/plans/2026-04-01-host-object-cli-first-implementation.md
git commit -m "feat: add host cli object entrypoint"
```

### Task 4 Summary

- [x] 已填写
- 已完成的工作：新增了 `ops.cli host` 第一版对象域和 `tests/test_host_cli.py`，把 `inventory`、`audit filesystem`、`remote bash`、`secrets sync-host-layout` 统一桥接到 `host inventory / audit / remote bash / secrets-layout`；同时更新了 `README.md`、`docs/architecture/control-plane.md`、`docs/runbooks/wsl-host-governance.md`、`.codex/skills/host-ops/SKILL.md` 与 `AGENTS.md`，把宿主机治理默认入口切到 `uv run python -m ops.cli host ...`。
- 兼容边界：旧 `inventory`、`audit filesystem`、`remote bash`、`secrets` 子命令仍保留可用，只降级为 compat / legacy stable path；`ops/scripts/remote/run_remote_bash.sh` 仍保持兼容层语义。
- 未并入的范围：`network / panel / firewall` 仍保留原域，没有在本轮并入 `host`。原因是第一版只做宿主机基础治理入口上收，不把基础宿主机对象面与 bridge network、1Panel 面板/防火墙对象面混在一起。
