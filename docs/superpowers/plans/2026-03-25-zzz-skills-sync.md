# ZZZ Skills Sync Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 `OP_Linux` 中落地 `zzz-skills` 镜像同步控制面，补齐 CLI、同步器、WSL inventory、runbook，并把 WSL 本机 1Panel 计划任务收敛成受管资产。

**Architecture:** 先通过测试锁定同步器与 CLI 行为，再实现 Python 同步模块与 `ops.cli automation` 入口，随后把 WSL inventory、runbook 与治理文档补齐，最后用 WSL 本机 1Panel API 校验并创建或更新 `wsl-zzz-skills-sync` 定时任务。同步逻辑只存在于 `OP_Linux`，1Panel 页面只保存统一命令入口与周期配置。

**Tech Stack:** Python (`uv`, `unittest`, `pytest`), `argparse`, Git CLI, filesystem mirroring, JSON inventory docs, WSL local 1Panel API

---

## File Structure

- Create: `ops/cli/automation.py`
  Responsibility: `ops.cli automation ...` 子命令定义与调用同步器的薄封装。
- Create: `ops/scripts/automation/__init__.py`
  Responsibility: automation 脚本包标记。
- Create: `ops/scripts/automation/sync_zzz_skills.py`
  Responsibility: 源目录扫描、镜像收敛、Git 预检、提交与推送、结果对象输出。
- Create: `tests/test_zzz_skills_sync.py`
  Responsibility: 覆盖同步器的核心行为，包括无变化跳过、镜像删除、allowlist、防脏工作树。
- Modify: `ops/cli/app.py`
  Responsibility: 注册 `automation` 顶层命令。
- Modify: `tests/test_cli_entrypoints.py`
  Responsibility: 断言 `automation` 帮助与 JSON 输出。
- Modify: `tests/test_inventory_generation.py`
  Responsibility: 断言 WSL inventory 中新增的受管自动化区块。
- Modify: `inventory/servers/wsl/inventory.json`
  Responsibility: 登记 `wsl-zzz-skills-sync` 任务的控制面资产。
- Create: `inventory/servers/wsl/README.md`
  Responsibility: 提供 WSL inventory 摘要与计划任务入口说明。
- Create: `docs/runbooks/wsl-zzz-skills-sync.md`
  Responsibility: 手动执行、故障排查、1Panel 任务核查与验收步骤。
- Modify: `docs/runbooks/wsl-host-governance.md`
  Responsibility: 写入“1Panel 只做调度，业务逻辑必须走 `ops.cli`”规则。
- Modify: `docs/architecture/linux-governance.md`
  Responsibility: 写入 WSL 本机自动化任务纳管原则。

### Task 1: 用测试锁定同步器与 CLI 边界

**Files:**
- Create: `tests/test_zzz_skills_sync.py`
- Modify: `tests/test_cli_entrypoints.py`
- Modify: `tests/test_inventory_generation.py`

- [ ] **Step 1: 写同步器的失败测试**

在 `tests/test_zzz_skills_sync.py` 新增最小用例，覆盖：

```python
def test_sync_reports_no_changes_when_target_matches_source(): ...
def test_sync_removes_stale_zzz_directories(): ...
def test_sync_rejects_dirty_git_worktree(): ...
def test_sync_rejects_unknown_root_files_outside_allowlist(): ...
```

断言重点：
- 仅同步 `zzz-*`
- 陈旧 `zzz-*` 目录会删除
- 脏工作树直接失败
- 未列入 allowlist 的仓库级文件触发失败

- [ ] **Step 2: 写 CLI 帮助和 JSON 输出的失败测试**

在 `tests/test_cli_entrypoints.py` 增加：

```python
self.assertIn("automation", result.stdout)
result = run_cli("automation", "sync-zzz-skills", "--help")
self.assertEqual(result.returncode, 0)
```

再加一个 JSON smoke test：

```python
result = run_cli(
    "automation",
    "sync-zzz-skills",
    "--repo-root",
    str(root),
    "--source-root",
    str(source_root),
    "--target-repo",
    str(target_repo),
)
payload = json.loads(result.stdout)
self.assertEqual("automation", payload["command"])
```

- [ ] **Step 3: 写 inventory 自动化区块的失败测试**

在 `tests/test_inventory_generation.py` 增加：

```python
self.assertIn("automations", payload)
self.assertEqual("wsl-zzz-skills-sync", payload["automations"][0]["name"])
```

- [ ] **Step 4: 运行测试确认先红**

Run: `cd /root/work/OP_Linux && uv run pytest tests/test_zzz_skills_sync.py tests/test_cli_entrypoints.py tests/test_inventory_generation.py -q`

Expected: FAIL，失败点来自缺少 `automation` 命令、缺少同步实现或 inventory 字段。

- [ ] **Step 5: Commit**

```bash
git add tests/test_zzz_skills_sync.py tests/test_cli_entrypoints.py tests/test_inventory_generation.py
git commit -m "test: define zzz skills sync behavior"
```

### Task 2: 实现同步器与 `ops.cli automation` 入口

**Files:**
- Create: `ops/cli/automation.py`
- Create: `ops/scripts/automation/__init__.py`
- Create: `ops/scripts/automation/sync_zzz_skills.py`
- Modify: `ops/cli/app.py`
- Test: `tests/test_zzz_skills_sync.py`
- Test: `tests/test_cli_entrypoints.py`

- [ ] **Step 1: 实现同步结果模型与预检**

在 `ops/scripts/automation/sync_zzz_skills.py` 定义最小接口，例如：

```python
def run_sync(
    *,
    source_root: Path,
    target_repo: Path,
    branch: str = "main",
    allowed_root_files: tuple[str, ...] = ("README.md", ".gitignore"),
) -> dict[str, Any]:
    ...
```

预检至少包含：
- `source_root` 存在
- `target_repo/.git` 存在
- 当前分支为 `main`
- `git status --short` 为空
- `origin/main` 不领先本地

- [ ] **Step 2: 实现镜像收敛逻辑**

最小实现包含：

```python
skill_dirs = sorted(path for path in source_root.iterdir() if path.is_dir() and path.name.startswith("zzz-"))
```

行为要求：
- 对每个源目录复制到目标仓库
- 删除目标仓库中多余的 `zzz-*` 目录
- 过滤 `.DS_Store`、`Thumbs.db`、`__pycache__`
- 遇到未知仓库级文件时失败，不静默删

- [ ] **Step 3: 实现 Git 提交与推送逻辑**

最小实现：

```python
if not has_changes(target_repo):
    return {"status": "ok_no_changes", ...}

run_git(["add", "-A"], cwd=target_repo)
run_git(["commit", "-m", "chore: sync zzz skills"], cwd=target_repo)
run_git(["push", "origin", branch], cwd=target_repo)
return {"status": "ok_pushed", ...}
```

- [ ] **Step 4: 接入 `ops.cli automation`**

在 `ops/cli/automation.py` 中提供：

```python
def add_automation_parser(subparsers): ...
def handle_automation_command(args): ...
```

在 `ops/cli/app.py` 中注册：

```python
automation_parser = subparsers.add_parser("automation", help="本机自动化任务")
```

并输出统一 JSON：

```python
{
  "command": "automation",
  "action": "sync-zzz-skills",
  "payload": {...}
}
```

- [ ] **Step 5: 运行测试确认变绿**

Run: `cd /root/work/OP_Linux && uv run pytest tests/test_zzz_skills_sync.py tests/test_cli_entrypoints.py tests/test_inventory_generation.py -q`

Expected: PASS

- [ ] **Step 6: 做一次本地 dry-run 验证**

Run: `cd /root/work/OP_Linux && uv run python -m ops.cli automation sync-zzz-skills --source-root /mnt/c/Users/Administrator/.codex/skills --target-repo /root/work/zzz-skills`

Expected: 返回 `ok_no_changes` 或 `ok_pushed` 的 JSON，不出现栈追踪。

- [ ] **Step 7: Commit**

```bash
git add ops/cli/automation.py ops/scripts/automation/__init__.py ops/scripts/automation/sync_zzz_skills.py ops/cli/app.py tests/test_zzz_skills_sync.py tests/test_cli_entrypoints.py
git commit -m "feat: add zzz skills sync automation"
```

### Task 3: 把 WSL inventory 与摘要文档纳入受管状态

**Files:**
- Modify: `inventory/servers/wsl/inventory.json`
- Create: `inventory/servers/wsl/README.md`
- Test: `tests/test_inventory_generation.py`

- [ ] **Step 1: 在 WSL inventory 中登记任务**

在 `inventory/servers/wsl/inventory.json` 增加顶层 `automations`，至少包含：

```json
{
  "name": "wsl-zzz-skills-sync",
  "controller": "1panel-cronjob",
  "schedule": "every 2 hours",
  "cwd": "/root/work/OP_Linux",
  "command": "uv run python -m ops.cli automation sync-zzz-skills",
  "source_root": "/mnt/c/Users/Administrator/.codex/skills",
  "target_repo": "/root/work/zzz-skills",
  "target_branch": "main"
}
```

- [ ] **Step 2: 新增 WSL inventory README**

在 `inventory/servers/wsl/README.md` 写入最小摘要：

```md
- 受管计划任务：`wsl-zzz-skills-sync`
- 控制器：`1Panel cronjob`
- 执行入口：`uv run python -m ops.cli automation sync-zzz-skills`
```

- [ ] **Step 3: 运行 inventory 相关测试**

Run: `cd /root/work/OP_Linux && uv run pytest tests/test_inventory_generation.py -q`

Expected: PASS

- [ ] **Step 4: 生成一次 inventory 快照做人工检查**

Run: `cd /root/work/OP_Linux && uv run python -m ops.cli inventory wsl --repo-root /root/work/OP_Linux`

Expected: 输出中包含 `automations` 与 `wsl-zzz-skills-sync`。

- [ ] **Step 5: Commit**

```bash
git add inventory/servers/wsl/inventory.json inventory/servers/wsl/README.md tests/test_inventory_generation.py
git commit -m "docs: register wsl zzz skills sync automation"
```

### Task 4: 补 runbook 与治理规则

**Files:**
- Create: `docs/runbooks/wsl-zzz-skills-sync.md`
- Modify: `docs/runbooks/wsl-host-governance.md`
- Modify: `docs/architecture/linux-governance.md`

- [ ] **Step 1: 写专用 runbook**

在 `docs/runbooks/wsl-zzz-skills-sync.md` 至少包含：
- 目的与边界
- 源/目标路径
- 手动执行命令
- `ok_no_changes` / `ok_pushed` / 失败状态含义
- 如何查看 WSL 1Panel 计划任务执行记录
- 工作树脏、push 失败、源目录缺失的排障步骤

- [ ] **Step 2: 更新 WSL 治理 runbook**

在 `docs/runbooks/wsl-host-governance.md` 加入一段明确规则：

```md
- WSL 本机 1Panel 计划任务只负责调度。
- 计划任务业务逻辑必须通过 `uv run python -m ops.cli ...` 承载。
- 新增本机计划任务时，必须同步更新 inventory 与 runbook。
```

- [ ] **Step 3: 更新 Linux 治理文档**

在 `docs/architecture/linux-governance.md` 增加一条自动化纳管规则，声明：
- 1Panel 页面中不放业务逻辑
- WSL 本机受管任务需要稳定命令入口、inventory 记录与文档入口

- [ ] **Step 4: 运行文档相关测试**

Run: `cd /root/work/OP_Linux && uv run pytest tests/test_docs_no_legacy_terms.py -q`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add docs/runbooks/wsl-zzz-skills-sync.md docs/runbooks/wsl-host-governance.md docs/architecture/linux-governance.md
git commit -m "docs: add wsl zzz skills sync runbook"
```

### Task 5: 在 WSL 本机 1Panel 校验并落地计划任务

**Files:**
- Runtime only: WSL local 1Panel cronjob `wsl-zzz-skills-sync`
- Reference: `secrets/services/onepanel-api.wsl.env`
- Reference: `docs/runbooks/wsl-zzz-skills-sync.md`

- [ ] **Step 1: 先用只读 API 确认现有 cronjob 状态**

Run: `cd /root/work/OP_Linux && python3 ops/scripts/onepanel/api_request.py POST /api/v2/cronjobs/search --env-file secrets/services/onepanel-api.wsl.env --body-json '<valid-search-payload>'`

Expected: 返回当前 WSL 1Panel cronjob 列表，可确认是否已存在 `wsl-zzz-skills-sync`。

- [ ] **Step 2: 确认创建或更新路径**

二选一，优先 API：
- 若验证出 `POST /api/v2/cronjobs` / `POST /api/v2/cronjobs/update` 的 payload，可用 API 创建或更新任务。
- 若 API mutation 形状仍不稳定，则通过浏览器在 WSL 本机 1Panel 页面手工创建一次，但命令必须严格写为：

```bash
cd /root/work/OP_Linux && uv run python -m ops.cli automation sync-zzz-skills
```

周期固定为每 2 小时一次，任务名固定为 `wsl-zzz-skills-sync`。

- [ ] **Step 3: 手动触发一次任务**

Expected:
- 1Panel 执行记录显示成功
- stdout/stderr 能看到同步器 JSON 结果
- `/root/work/zzz-skills` 状态符合当前源目录

- [ ] **Step 4: 记录最终运行证据到 inventory / runbook**

把最终确认到的任务名、周期、入口命令和检查方式与仓库文档一致化；若实现时发现 UI 名称或 schedule 文案与预期不同，先更新文档再结束。

- [ ] **Step 5: 做最终回归验证**

Run:
- `cd /root/work/OP_Linux && uv run pytest tests/test_zzz_skills_sync.py tests/test_cli_entrypoints.py tests/test_inventory_generation.py tests/test_docs_no_legacy_terms.py -q`
- `cd /root/work/OP_Linux && uv run python -m ops.cli automation sync-zzz-skills --source-root /mnt/c/Users/Administrator/.codex/skills --target-repo /root/work/zzz-skills`

Expected:
- 测试全绿
- CLI 成功返回 `ok_no_changes` 或 `ok_pushed`
- WSL 1Panel 中存在可复用的 `wsl-zzz-skills-sync`

- [ ] **Step 6: Commit**

```bash
git add inventory/servers/wsl/inventory.json inventory/servers/wsl/README.md docs/runbooks/wsl-zzz-skills-sync.md docs/runbooks/wsl-host-governance.md docs/architecture/linux-governance.md
git commit -m "chore: manage wsl zzz skills sync task"
```
