# Host V2 Network-Only Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把受管 Docker bridge 网络治理正式迁入 `uv run python -m ops.cli host network ...`，删除旧顶层 `network` 入口，并同步收口 active 文档与测试口径。

**Architecture:** 继续保持 `host` 作为宿主机真源对象域，`network` 以 `host` 子域形式存在；不再保留顶层 `network` parser/handler，也不保留 `compat_source`。网络治理算法本身尽量不动，只做对象域迁移与正式入口收口。

**Tech Stack:** Python 3、`argparse`、`pytest`/`unittest`、repo-local Markdown docs、Git worktree

---

## File Map

- Modify: `ops/cli/app.py`
- Modify: `ops/cli/host.py`
- Modify: `ops/cli/networks.py`
- Modify: `tests/test_cli_entrypoints.py`
- Modify: `tests/test_host_cli.py`
- Modify: `tests/test_app_cli.py`
- Modify: `tests/test_docs_no_legacy_terms.py`
- Modify: `README.md`
- Modify: `AGENTS.md`
- Modify: `docs/architecture/control-plane.md`
- Modify: `docs/runbooks/wsl-host-governance.md`
- Modify: `docs/runbooks/app-project-delivery-workflow.md`
- Modify: `.codex/skills/host-ops/SKILL.md`

### Task 1: 先冻结 `host network` CLI 合同

**Files:**
- Modify: `tests/test_cli_entrypoints.py`
- Modify: `tests/test_host_cli.py`

- [ ] **Step 1: 写失败测试，移除顶层 `network` 预期并新增 `host network` 预期**

在 `tests/test_cli_entrypoints.py` 中把 help 合同改成：

```python
result = run_cli("--help")
self.assertNotIn("\n  network", result.stdout)

host_help = run_cli("host", "--help")
self.assertIn("network", host_help.stdout)

host_network_help = run_cli("host", "network", "--help")
self.assertIn("audit", host_network_help.stdout)
self.assertIn("ensure", host_network_help.stdout)
```

- [ ] **Step 2: 在 `tests/test_host_cli.py` 新增 `host network audit|ensure` 合同测试**

新增最小测试：

```python
result = run_cli("host", "network", "audit", "prod2-main", "--repo-root", str(root))
payload = json.loads(result.stdout)
self.assertEqual("host", payload["command"])
self.assertEqual("network.audit", payload["action"])
self.assertEqual("prod2-main", payload["target"])
self.assertIsInstance(payload["payload"], dict)
```

以及：

```python
result = run_cli("host", "network", "ensure", "prod2-main", "--repo-root", str(root))
payload = json.loads(result.stdout)
self.assertEqual("host", payload["command"])
self.assertEqual("network.ensure", payload["action"])
self.assertEqual("prod2-main", payload["target"])
```

- [ ] **Step 3: 运行定向测试确认先红**

Run:

```bash
cd /root/work/OP_Linux/.worktrees/codex-cli-first-repo-refactor
uv run python -m pytest tests/test_cli_entrypoints.py tests/test_host_cli.py -q
```

Expected:
- `host network` 测试失败
- 失败原因是命令尚未迁入 `host`，不是测试拼写错误

### Task 2: 迁移网络 parser 与返回形状到 `host`

**Files:**
- Modify: `ops/cli/host.py`
- Modify: `ops/cli/networks.py`
- Modify: `ops/cli/app.py`

- [ ] **Step 1: 在 `ops/cli/host.py` 添加 `network` 子解析器**

目标形状：

```python
network_parser = host_subparsers.add_parser("network", help="受管 Docker bridge 网络治理")
network_subparsers = network_parser.add_subparsers(dest="host_network_action", required=True)

audit = network_subparsers.add_parser("audit", help="审计受管 bridge 网络")
audit.add_argument("target", choices=SUPPORTED_NETWORK_TARGETS, help="目标环境")
audit.add_argument("--repo-root", default=".", help="仓库根目录")

ensure = network_subparsers.add_parser("ensure", help="修复受管 bridge 网络漂移")
ensure.add_argument("target", choices=SUPPORTED_NETWORK_TARGETS, help="目标环境")
ensure.add_argument("--repo-root", default=".", help="仓库根目录")
```

- [ ] **Step 2: 在 `handle_host_command(...)` 中接入网络动作**

最小返回形状：

```python
if args.host_action == "network" and args.host_network_action == "audit":
    return {
        "command": "host",
        "action": "network.audit",
        "target": args.target,
        "payload": audit_managed_bridge_networks(repo_root, args.target),
    }
```

以及：

```python
if args.host_action == "network" and args.host_network_action == "ensure":
    return {
        "command": "host",
        "action": "network.ensure",
        "target": args.target,
        "payload": ensure_managed_bridge_networks(repo_root, args.target),
    }
```

- [ ] **Step 3: 从 `ops/cli/app.py` 删除顶层 `network` parser/handler**

删除：

```python
add_network_parser(subparsers)
```

以及：

```python
if args.command == "network":
    ...
```

- [ ] **Step 4: 把 `ops/cli/networks.py` 收紧成纯实现模块**

保留：

```python
audit_managed_bridge_networks(...)
ensure_managed_bridge_networks(...)
```

删除：

```python
add_network_parser(...)
handle_network_command(...)
```

- [ ] **Step 5: 运行定向测试确认转绿**

Run:

```bash
cd /root/work/OP_Linux/.worktrees/codex-cli-first-repo-refactor
uv run python -m pytest tests/test_cli_entrypoints.py tests/test_host_cli.py -q
```

Expected:
- `host network` 合同通过
- 顶层 `network` 已从帮助中消失

### Task 3: 把既有网络行为测试迁到正式入口

**Files:**
- Modify: `tests/test_app_cli.py`

- [ ] **Step 1: 把 `network audit`/`network ensure` CLI 用例改成 `host network audit|ensure`**

示例替换：

```python
result = run_cli(
    "host",
    "network",
    "audit",
    "prod2-main",
    "--repo-root",
    str(root),
)
```

和：

```python
result = run_cli(
    "host",
    "network",
    "ensure",
    "prod2-main",
    "--repo-root",
    str(root),
)
```

- [ ] **Step 2: 更新返回断言**

断言改为：

```python
self.assertEqual("host", payload["command"])
self.assertEqual("network.audit", payload["action"])
```

以及：

```python
self.assertEqual("host", payload["command"])
self.assertEqual("network.ensure", payload["action"])
```

- [ ] **Step 3: 运行 focused tests**

Run:

```bash
cd /root/work/OP_Linux/.worktrees/codex-cli-first-repo-refactor
uv run python -m pytest tests/test_app_cli.py -q
```

Expected:
- 原网络治理行为测试继续通过
- 不因对象域迁移而改变 repair 逻辑

### Task 4: 同步 active 文档、仓库规则与 skill

**Files:**
- Modify: `README.md`
- Modify: `AGENTS.md`
- Modify: `docs/architecture/control-plane.md`
- Modify: `docs/runbooks/wsl-host-governance.md`
- Modify: `docs/runbooks/app-project-delivery-workflow.md`
- Modify: `.codex/skills/host-ops/SKILL.md`
- Modify: `tests/test_docs_no_legacy_terms.py`

- [ ] **Step 1: 把 active 文档中的正式入口改成 `host network`**

替换方向：

```md
uv run python -m ops.cli host network audit <target> --repo-root /root/work/OP_Linux
uv run python -m ops.cli host network ensure <target> --repo-root /root/work/OP_Linux
```

- [ ] **Step 2: 删除“`network / panel / firewall` 都属于下一阶段桥接对象”这类过时表述**

改成：

```md
`network` 已并入 `host`；
`panel / firewall` 仍保留在 `onepanel` 域。
```

- [ ] **Step 3: 收紧文档合同测试**

更新 `tests/test_docs_no_legacy_terms.py`，确保 active 文档：

```python
self.assertNotIn("uv run python -m ops.cli network ", text)
self.assertIn("uv run python -m ops.cli host network ", text)
```

- [ ] **Step 4: 运行文档相关回归**

Run:

```bash
cd /root/work/OP_Linux/.worktrees/codex-cli-first-repo-refactor
uv run python -m pytest tests/test_docs_no_legacy_terms.py tests/test_wsl_first_docs.py -q
```

Expected:
- active 文档合同通过
- 不影响 archive/history 里的历史材料

### Task 5: 最小全链路回归

**Files:**
- Verify: `ops/cli/host.py`
- Verify: `ops/cli/networks.py`
- Verify: `tests/test_cli_entrypoints.py`
- Verify: `tests/test_host_cli.py`
- Verify: `tests/test_app_cli.py`
- Verify: `tests/test_docs_no_legacy_terms.py`

- [ ] **Step 1: 运行核心定向回归**

Run:

```bash
cd /root/work/OP_Linux/.worktrees/codex-cli-first-repo-refactor
uv run python -m pytest \
  tests/test_cli_entrypoints.py \
  tests/test_host_cli.py \
  tests/test_app_cli.py \
  tests/test_docs_no_legacy_terms.py \
  tests/test_wsl_first_docs.py \
  -q
```

Expected:
- 全部通过

- [ ] **Step 2: 运行手工 smoke**

Run:

```bash
cd /root/work/OP_Linux/.worktrees/codex-cli-first-repo-refactor
uv run python -m ops.cli --help
uv run python -m ops.cli host --help
uv run python -m ops.cli host network audit prod2-main --repo-root /root/work/OP_Linux/.worktrees/codex-cli-first-repo-refactor
```

Expected:
- 顶层 help 不再出现 `network`
- `host` help 出现 `network`
- `host network audit` 返回结构化 JSON

- [ ] **Step 3: 审核变更范围**

Run:

```bash
cd /root/work/OP_Linux/.worktrees/codex-cli-first-repo-refactor
git status --short
```

Expected:
- 只包含计划内文件
