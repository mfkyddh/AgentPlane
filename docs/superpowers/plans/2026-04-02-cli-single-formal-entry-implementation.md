# CLI Single Formal Entry Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 硬删除 `inventory / audit / remote / secrets` 顶层 CLI 入口，只保留 `host` 作为宿主机正式入口，并把 `host secrets` 变成唯一 secrets 正式入口，同时同步收口 active 文档、skills、帮助输出与测试口径。

**Architecture:** 继续复用现有 `inventory`、`audit`、`remote`、`secrets` 底层函数，但不再把它们暴露为顶层 parser。`ops.cli host` 成为唯一宿主机公开对象面，由它负责把旧 helper 的输出整理成统一的 `{command, action, target, payload}` 正式合同，并删除 `compat_source` 与旧顶层公开语义泄漏。

**Tech Stack:** Python 3、`argparse`、repo-local `unittest`/`pytest`、Markdown docs/skills、Bash wrapper

---

## File Map

- Modify: `ops/cli/app.py`
- Modify: `ops/cli/host.py`
- Modify: `ops/cli/remote.py`
- Modify: `ops/cli/secrets.py`
- Modify: `ops/scripts/remote/run_remote_bash.sh`
- Modify: `tests/test_cli_entrypoints.py`
- Modify: `tests/test_host_cli.py`
- Modify: `tests/test_secrets_cli.py`
- Modify: `tests/test_inventory_generation.py`
- Modify: `tests/test_prod0_audit.py`
- Modify: `tests/test_docs_no_legacy_terms.py`
- Modify: `README.md`
- Modify: `AGENTS.md`
- Modify: `docs/runbooks/bootstrap-secrets.md`
- Modify: `docs/runbooks/control-plane-domain-onboarding.md`
- Modify: `docs/runbooks/wsl-host-governance.md`
- Modify: `docs/runbooks/powershell-wsl-remote-bash.md`
- Modify: `docs/runbooks/prod0-main-governance.md`
- Modify: `docs/runbooks/control-plane-legacy-migration.md`
- Modify: `.codex/skills/host-ops/SKILL.md`
- Modify: `.codex/skills/app-resource-ops/SKILL.md`

### Task 1: 先冻结新的 CLI 合同与旧入口退场测试

**Files:**
- Modify: `tests/test_cli_entrypoints.py`
- Modify: `tests/test_host_cli.py`
- Modify: `tests/test_secrets_cli.py`
- Modify: `tests/test_inventory_generation.py`
- Modify: `tests/test_prod0_audit.py`

- [ ] **Step 1: 把顶层 help 合同改成“不再暴露旧入口”**

在 `tests/test_cli_entrypoints.py` 中把 `--help` 断言改成只保留正式入口，并把 `host` 的子命令断言改成 `secrets` 子命令族：

```python
result = run_cli("--help")
self.assertEqual(result.returncode, 0, msg=result.stderr)
self.assertIn("host", result.stdout)
self.assertIn("service", result.stdout)
self.assertIn("website", result.stdout)
self.assertIn("tenant", result.stdout)
self.assertIn("app", result.stdout)
self.assertIn("projection", result.stdout)
self.assertIn("cleanup", result.stdout)
self.assertIn("automation", result.stdout)
self.assertIn("onepanel", result.stdout)
self.assertNotIn("\n  inventory", result.stdout)
self.assertNotIn("\n  audit", result.stdout)
self.assertNotIn("\n  remote", result.stdout)
self.assertNotIn("\n  secrets", result.stdout)

host_help = run_cli("host", "--help")
self.assertIn("inventory", host_help.stdout)
self.assertIn("audit", host_help.stdout)
self.assertIn("network", host_help.stdout)
self.assertIn("remote", host_help.stdout)
self.assertIn("secrets", host_help.stdout)
self.assertNotIn("secrets-layout", host_help.stdout)

host_secrets_help = run_cli("host", "secrets", "--help")
self.assertIn("init-data-services", host_secrets_help.stdout)
self.assertIn("sync-layout", host_secrets_help.stdout)
```

- [ ] **Step 2: 把 `host` 合同测试改成正式 envelope，不再接受 `compat_source`**

在 `tests/test_host_cli.py` 中把 inventory/audit/remote/secrets 断言统一成正式形状：

```python
payload = json.loads(result.stdout)
self.assertEqual("host", payload["command"])
self.assertEqual("inventory", payload["action"])
self.assertEqual("wsl", payload["target"])
self.assertNotIn("compat_source", payload)
self.assertIsInstance(payload["payload"], dict)
```

以及：

```python
payload = json.loads(result.stdout)
self.assertEqual("host", payload["command"])
self.assertEqual("secrets.init-data-services", payload["action"])
self.assertEqual("prod0-main", payload["target"])
self.assertNotIn("compat_source", payload)
self.assertIn("files", payload["payload"])
```

同步新增旧入口退场断言：

```python
for argv in (
    ("inventory", "wsl"),
    ("audit", "filesystem", "--env", "wsl"),
    ("remote", "bash", "prod0-main", "--dry-run"),
    ("secrets", "init-data-services", "--target", "wsl"),
):
    result = run_cli(*argv)
    self.assertNotEqual(0, result.returncode)
    self.assertIn("invalid choice", result.stderr)
```

- [ ] **Step 3: 把仍直接跑旧顶层命令的测试切到 `host`**

在 `tests/test_secrets_cli.py`、`tests/test_inventory_generation.py`、`tests/test_prod0_audit.py` 中替换调用：

```python
result = run_cli("host", "inventory", "wsl", "--repo-root", str(REPO_ROOT))
```

```python
result = run_cli("host", "audit", "prod0-main", "--repo-root", str(root))
```

```python
result = run_cli(
    "host",
    "secrets",
    "init-data-services",
    "prod0-main",
    "--repo-root",
    str(root),
)
```

并把返回断言从旧顶层形状改成：

```python
self.assertEqual("host", payload["command"])
self.assertEqual("audit", payload["action"])
self.assertEqual("prod0-main", payload["target"])
self.assertIn("violations", payload["payload"])
```

- [ ] **Step 4: 运行定向测试，确认它们先红在新合同上**

Run:

```bash
cd /root/work/OP_Linux
uv run python -m pytest \
  tests/test_cli_entrypoints.py \
  tests/test_host_cli.py \
  tests/test_secrets_cli.py \
  tests/test_inventory_generation.py \
  tests/test_prod0_audit.py -q
```

Expected:
- 失败点集中在旧顶层 parser 仍存在
- `host secrets` 形状尚未落地
- `compat_source` 仍然出现在 `host` 输出里

- [ ] **Step 5: 提交测试冻结变更**

```bash
cd /root/work/OP_Linux
git add \
  tests/test_cli_entrypoints.py \
  tests/test_host_cli.py \
  tests/test_secrets_cli.py \
  tests/test_inventory_generation.py \
  tests/test_prod0_audit.py
git commit -m "test: freeze single formal cli entry contract"
```

### Task 2: 删除顶层 parser/dispatch，并把 `host` 变成唯一公开入口

**Files:**
- Modify: `ops/cli/app.py`
- Modify: `ops/cli/host.py`

- [ ] **Step 1: 从 `ops/cli/app.py` 删除旧顶层 parser 注册与 dispatch**

删除顶层 `inventory / audit / remote / secrets` 的 import、parser 注册和 handler 分支，只保留 `host` 与其他正式域：

```python
from ops.cli.host import add_host_parser, handle_host_command
from ops.cli.cleanup import apply_cleanup_plan, build_cleanup_plan
from ops.cli.automation import add_automation_parser, handle_automation_command
from ops.cli.onepanel import add_onepanel_parser, handle_onepanel_command, onepanel_error_payload, render_onepanel_text
from ops.cli.projection import add_projection_parser, handle_projection_command
from ops.cli.service import add_service_parser, handle_service_command
from ops.cli.tenant import add_tenant_parser, handle_tenant_command
from ops.cli.website import add_website_parser, handle_website_command
```

以及：

```python
subparsers = parser.add_subparsers(dest="command", required=True)
add_automation_parser(subparsers)
add_onepanel_parser(subparsers)
add_host_parser(subparsers)
add_service_parser(subparsers)
add_website_parser(subparsers)
add_app_parser(subparsers)
add_projection_parser(subparsers)
add_tenant_parser(subparsers)
```

- [ ] **Step 2: 把 `remote bash` 参数切分辅助函数收紧到 `host remote bash`**

在 `ops/cli/app.py` 中删掉顶层 `remote` 的切分分支，只保留 `host`：

```python
def _split_remote_bash_remainder(argv: list[str]) -> tuple[list[str], list[str]]:
    if argv[:3] != ["host", "remote", "bash"]:
        return argv, []
    if "--" not in argv:
        return argv, []
    separator = argv.index("--")
    if separator < 3:
        return argv, []
    return argv[:separator], argv[separator + 1 :]
```

- [ ] **Step 3: 在 `ops/cli/host.py` 新增 `host secrets` 子命令族并统一 envelope**

把 `secrets-layout` 替换成 `secrets` 子命令族：

```python
secrets_parser = host_subparsers.add_parser("secrets", help="主机级 secrets 正式入口")
secrets_subparsers = secrets_parser.add_subparsers(dest="host_secrets_action", required=True)

init_parser = secrets_subparsers.add_parser("init-data-services", help="初始化 PostgreSQL/Redis/MinIO 管理员凭据")
init_parser.add_argument("target", choices=SUPPORTED_HOST_TARGETS, help="目标环境")
init_parser.add_argument("--repo-root", default=".", help="仓库根目录")
init_parser.add_argument("--force", action="store_true", help="覆盖已存在的目标 secrets 文件")

sync_parser = secrets_subparsers.add_parser("sync-layout", help="从 host-first secrets 真源投影旧布局")
sync_parser.add_argument("target", choices=SUPPORTED_HOST_TARGETS, help="目标环境")
sync_parser.add_argument("--repo-root", default=".", help="仓库根目录")
sync_parser.add_argument("--write", action="store_true", help="写入投影路径")
```

同时把 envelope helper 收口成不再输出 `compat_source`：

```python
def _wrap(*, action: str, target: str, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "command": "host",
        "action": action,
        "target": target,
        "payload": payload,
    }
```

- [ ] **Step 4: 在 `handle_host_command(...)` 中屏蔽旧公开语义泄漏**

不要直接把 `generate_inventory_snapshot()` 或 `audit_filesystem()` 的顶层对象整块塞进 `payload`；只提取正式业务部分：

```python
if args.host_action == "inventory":
    inventory_result = generate_inventory_snapshot(repo_root, args.target, write=bool(args.write))
    return _wrap(
        action="inventory",
        target=args.target,
        payload={
            "inventory_file": inventory_result["inventory_file"],
            "snapshot": inventory_result["payload"],
        },
    )
```

```python
if args.host_action == "audit":
    audit_result = audit_filesystem(repo_root, args.target)
    return _wrap(
        action="audit",
        target=args.target,
        payload={
            "ok": audit_result["ok"],
            "violations": audit_result["violations"],
            "repo_root": audit_result["repo_root"],
        },
    )
```

`remote` 与 `secrets` 也按同样原则处理：

```python
if args.host_action == "remote" and args.host_remote_action == "bash":
    remote_result = execute_remote_bash(
        repo_root=repo_root,
        target=args.target,
        remote_args=list(args.remote_args),
        script_file=args.script_file,
        dry_run=bool(args.dry_run),
    )
    return _wrap(
        action="remote.bash",
        target=args.target,
        payload={
            key: value
            for key, value in remote_result.items()
            if key not in {"command", "action", "target"}
        },
    )
```

```python
if args.host_action == "secrets" and args.host_secrets_action == "init-data-services":
    secret_result = init_data_services(repo_root, args.target, force=bool(args.force))
    return _wrap(
        action="secrets.init-data-services",
        target=args.target,
        payload={
            key: value
            for key, value in secret_result.items()
            if key not in {"command", "action", "target"}
        },
    )
```

```python
if args.host_action == "secrets" and args.host_secrets_action == "sync-layout":
    secret_result = materialize_legacy_host_layout(repo_root, args.target, write=bool(args.write))
    return _wrap(
        action="secrets.sync-layout",
        target=args.target,
        payload={
            key: value
            for key, value in secret_result.items()
            if key not in {"command", "action", "target"}
        },
    )
```

- [ ] **Step 5: 运行 CLI 与 host 定向测试，确认帮助输出和 envelope 转绿**

Run:

```bash
cd /root/work/OP_Linux
uv run python -m pytest tests/test_cli_entrypoints.py tests/test_host_cli.py -q
uv run python -m ops.cli --help
uv run python -m ops.cli host --help
uv run python -m ops.cli host secrets --help
```

Expected:
- 顶层 help 不再出现 `inventory / audit / remote / secrets`
- `host --help` 只暴露 `inventory / audit / network / remote / secrets`
- `host secrets --help` 暴露 `init-data-services / sync-layout`

- [ ] **Step 6: 提交公开入口切换变更**

```bash
cd /root/work/OP_Linux
git add ops/cli/app.py ops/cli/host.py
git commit -m "feat: make host the sole formal host entrypoint"
```

### Task 3: 把 `remote` / `secrets` 收紧成内部实现模块

**Files:**
- Modify: `ops/cli/remote.py`
- Modify: `ops/cli/secrets.py`
- Modify: `ops/scripts/remote/run_remote_bash.sh`

- [ ] **Step 1: 从 `ops/cli/remote.py` 删除顶层 parser/handler，只保留执行 substrate**

删掉：

```python
def add_remote_parser(...): ...
def handle_remote_command(...): ...
```

保留：

```python
def execute_remote_bash(
    *,
    repo_root: Path,
    target: str,
    remote_args: list[str] | None = None,
    script_file: str | Path | None = None,
    stdin_text: str | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    ...
```

- [ ] **Step 2: 从 `ops/cli/secrets.py` 删除顶层 parser/handler，只保留底层 secrets helpers**

删掉：

```python
def add_secrets_parser(...): ...
def handle_secrets_command(...): ...
```

保留：

```python
SUPPORTED_SECRET_TARGETS = tuple(TARGET_ALIASES.keys())
def init_data_services(repo_root: Path, target: str, *, force: bool) -> dict[str, Any]: ...
def materialize_legacy_host_layout(repo_root: Path, target: str, *, write: bool) -> dict[str, Any]: ...
```

- [ ] **Step 3: 把远端 wrapper 切到 `host remote bash`，并弱化旧入口文案**

在 `ops/scripts/remote/run_remote_bash.sh` 中把说明与执行命令改成 `host remote bash`：

```bash
# Historical wrapper for callers that still shell out. Formal entrypoint is `uv run python -m ops.cli host remote bash ...`.
```

以及：

```bash
cmd=(python3 -m ops.cli host remote bash "$host" --repo-root "$REPO_ROOT")
```

`usage()` 中不要再把 `uv run python -m ops.cli remote bash ...` 写成推荐命令。

- [ ] **Step 4: 运行 secrets / inventory / audit 相关测试，确认内部 API 仍可复用**

Run:

```bash
cd /root/work/OP_Linux
uv run python -m pytest \
  tests/test_secrets_cli.py \
  tests/test_inventory_generation.py \
  tests/test_prod0_audit.py -q
```

Expected:
- 旧顶层命令测试已全部切到 `host`
- `host` 仍能稳定复用现有 inventory/audit/secrets/remote 底层能力

- [ ] **Step 5: 提交内部模块收紧变更**

```bash
cd /root/work/OP_Linux
git add ops/cli/remote.py ops/cli/secrets.py ops/scripts/remote/run_remote_bash.sh
git commit -m "refactor: retire top-level remote and secrets entrypoints"
```

### Task 4: 收口 active 文档、skills 与文档测试口径

**Files:**
- Modify: `README.md`
- Modify: `AGENTS.md`
- Modify: `docs/runbooks/bootstrap-secrets.md`
- Modify: `docs/runbooks/control-plane-domain-onboarding.md`
- Modify: `docs/runbooks/wsl-host-governance.md`
- Modify: `docs/runbooks/powershell-wsl-remote-bash.md`
- Modify: `docs/runbooks/prod0-main-governance.md`
- Modify: `docs/runbooks/control-plane-legacy-migration.md`
- Modify: `.codex/skills/host-ops/SKILL.md`
- Modify: `.codex/skills/app-resource-ops/SKILL.md`
- Modify: `tests/test_docs_no_legacy_terms.py`

- [ ] **Step 1: 把 active 文档里的旧命令全部换成 `host` 正式入口**

替换示例：

```md
`uv run python -m ops.cli host inventory prod0-main`
`uv run python -m ops.cli host audit prod0-main --repo-root /root/work/OP_Linux`
`uv run python -m ops.cli host secrets init-data-services wsl --repo-root /root/work/OP_Linux`
`uv run python -m ops.cli host secrets sync-layout wsl --repo-root /root/work/OP_Linux --write`
```

`README.md`、`bootstrap-secrets.md`、`control-plane-domain-onboarding.md`、`prod0-main-governance.md` 中不要再出现：

```text
uv run python -m ops.cli inventory ...
uv run python -m ops.cli audit filesystem ...
uv run python -m ops.cli remote bash ...
uv run python -m ops.cli secrets ...
```

- [ ] **Step 2: 把 `AGENTS.md` 与 skills 中的“compatibility-only”口径删成正式事实**

把 `AGENTS.md` 改成只声明正式入口：

```md
- Formal host-scoped network governance must prefer `uv run python -m ops.cli host network ...`.
- Formal host-scoped remote execution must prefer `uv run python -m ops.cli host remote bash ...`.
- Formal host-scoped secrets operations must prefer `uv run python -m ops.cli host secrets ...`.
```

把 `.codex/skills/host-ops/SKILL.md` 和 `.codex/skills/app-resource-ops/SKILL.md` 改成：

```bash
uv run python -m ops.cli host secrets init-data-services <target> --repo-root /root/work/OP_Linux
uv run python -m ops.cli host secrets sync-layout <target> --repo-root /root/work/OP_Linux --write
```

- [ ] **Step 3: 把 `control-plane-legacy-migration.md` 降格成历史迁移说明**

不要再把旧入口写成当前可执行替代项；用“历史迁移示意”表述：

```md
历史迁移期间曾存在 `uv run python -m ops.cli remote bash ...`、`uv run python -m ops.cli inventory ...` 等顶层入口；当前正式入口已收口到对象域与 `host` 子域，不再接受这些命令。
```

并把“最小命令示例”改成当前事实：

```bash
uv run python -m ops.cli host remote bash prod0-main --repo-root /root/work/OP_Linux --dry-run
uv run python -m ops.cli host inventory prod0-main --repo-root /root/work/OP_Linux
```

- [ ] **Step 4: 把文档测试从“允许 compat 说明”改成“只允许正式入口”**

在 `tests/test_docs_no_legacy_terms.py` 中更新常量与断言：

```python
HOST_WSL_RUNBOOK_ENTRYPOINTS = (
    "uv run python -m ops.cli host audit wsl --repo-root /root/work/OP_Linux",
    "uv run python -m ops.cli host inventory wsl --repo-root /root/work/OP_Linux",
    "uv run python -m ops.cli host network audit prod2-main --repo-root /root/work/OP_Linux",
    "uv run python -m ops.cli host network ensure prod2-main --repo-root /root/work/OP_Linux",
    "uv run python -m ops.cli host remote bash prod0-main --dry-run --script-file /root/work/OP_Linux/ops/scripts/internal/remote/example.sh",
    "uv run python -m ops.cli host secrets sync-layout wsl --repo-root /root/work/OP_Linux",
)
```

并新增禁止项：

```python
for legacy in (
    "uv run python -m ops.cli inventory",
    "uv run python -m ops.cli audit filesystem",
    "uv run python -m ops.cli remote bash",
    "uv run python -m ops.cli secrets ",
    "host secrets-layout",
):
    self.assertNotIn(legacy, text)
```

- [ ] **Step 5: 运行文档测试并做一次全仓 grep 自检**

Run:

```bash
cd /root/work/OP_Linux
uv run python -m pytest tests/test_docs_no_legacy_terms.py -q
rg -n -F "uv run python -m ops.cli inventory" README.md AGENTS.md docs/runbooks .codex/skills
rg -n -F "uv run python -m ops.cli audit filesystem" README.md AGENTS.md docs/runbooks .codex/skills
rg -n -F "uv run python -m ops.cli remote bash" README.md AGENTS.md docs/runbooks .codex/skills
rg -n -F "uv run python -m ops.cli secrets" README.md AGENTS.md docs/runbooks .codex/skills
rg -n -F "host secrets-layout" README.md AGENTS.md docs/runbooks .codex/skills
```

Expected:
- 文档测试通过
- `rg` 结果只允许出现在历史 spec/plan/archive，不出现在 active 文档与 skills

- [ ] **Step 6: 提交文档与 skill 收口变更**

```bash
cd /root/work/OP_Linux
git add \
  README.md \
  AGENTS.md \
  docs/runbooks/bootstrap-secrets.md \
  docs/runbooks/control-plane-domain-onboarding.md \
  docs/runbooks/wsl-host-governance.md \
  docs/runbooks/powershell-wsl-remote-bash.md \
  docs/runbooks/prod0-main-governance.md \
  docs/runbooks/control-plane-legacy-migration.md \
  .codex/skills/host-ops/SKILL.md \
  .codex/skills/app-resource-ops/SKILL.md \
  tests/test_docs_no_legacy_terms.py
git commit -m "docs: remove legacy top-level cli references"
```

### Task 5: 做最终回归验证与收口

**Files:**
- Modify: `ops/cli/app.py`
- Modify: `ops/cli/host.py`
- Modify: `ops/cli/remote.py`
- Modify: `ops/cli/secrets.py`
- Modify: `ops/scripts/remote/run_remote_bash.sh`
- Modify: `tests/test_cli_entrypoints.py`
- Modify: `tests/test_host_cli.py`
- Modify: `tests/test_secrets_cli.py`
- Modify: `tests/test_inventory_generation.py`
- Modify: `tests/test_prod0_audit.py`
- Modify: `tests/test_docs_no_legacy_terms.py`

- [ ] **Step 1: 运行本轮最小完整测试集**

Run:

```bash
cd /root/work/OP_Linux
uv run python -m pytest \
  tests/test_cli_entrypoints.py \
  tests/test_host_cli.py \
  tests/test_secrets_cli.py \
  tests/test_inventory_generation.py \
  tests/test_prod0_audit.py \
  tests/test_docs_no_legacy_terms.py -q
```

Expected:
- 所有本轮 CLI、文档、host 合同测试通过

- [ ] **Step 2: 手工核对帮助输出与旧入口错误**

Run:

```bash
cd /root/work/OP_Linux
uv run python -m ops.cli --help
uv run python -m ops.cli host --help
uv run python -m ops.cli host secrets --help
uv run python -m ops.cli inventory wsl
uv run python -m ops.cli audit filesystem --env wsl
uv run python -m ops.cli remote bash prod0-main --dry-run
uv run python -m ops.cli secrets init-data-services --target wsl
```

Expected:
- 前三个命令成功
- 后四个命令由 `argparse` 直接报 unknown/invalid choice

- [ ] **Step 3: 自检实现是否仍有历史兼容痕迹**

Run:

```bash
cd /root/work/OP_Linux
rg -n "compat_source" ops tests
rg -n -F "add_remote_parser" ops
rg -n -F "add_secrets_parser" ops
rg -n -F "handle_remote_command" ops
rg -n -F "handle_secrets_command" ops
```

Expected:
- `compat_source` 不再出现在 `ops/cli/host.py` 与相关合同测试中
- 顶层 `remote` / `secrets` parser/handler 已不存在

- [ ] **Step 4: 提交最终收口**

```bash
cd /root/work/OP_Linux
git add \
  ops/cli/app.py \
  ops/cli/host.py \
  ops/cli/remote.py \
  ops/cli/secrets.py \
  ops/scripts/remote/run_remote_bash.sh \
  tests/test_cli_entrypoints.py \
  tests/test_host_cli.py \
  tests/test_secrets_cli.py \
  tests/test_inventory_generation.py \
  tests/test_prod0_audit.py \
  tests/test_docs_no_legacy_terms.py \
  README.md \
  AGENTS.md \
  docs/runbooks/bootstrap-secrets.md \
  docs/runbooks/control-plane-domain-onboarding.md \
  docs/runbooks/wsl-host-governance.md \
  docs/runbooks/powershell-wsl-remote-bash.md \
  docs/runbooks/prod0-main-governance.md \
  docs/runbooks/control-plane-legacy-migration.md \
  .codex/skills/host-ops/SKILL.md \
  .codex/skills/app-resource-ops/SKILL.md
git commit -m "feat: hard-delete legacy top-level cli entrypoints"
```
