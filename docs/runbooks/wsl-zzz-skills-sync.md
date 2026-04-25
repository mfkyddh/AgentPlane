---
status: active
owner: AgentPlane maintainers
last_verified: 2026-04-25
superseded_by: null
---

# 🔄 WSL ZZZ Skills Sync

结论：WSL 本机 `zzz-skills` 镜像同步的正式入口是 `agentplane infra automation apply ...`，1Panel 计划任务只是调度器。

## 🎯 Purpose

统一管理 WSL 本机 `zzz-skills` 镜像同步。正式执行入口是仓库 CLI；1Panel 计划任务只是调度器，不是业务实现。

## Scope

| 项目 | 值 |
| --- | --- |
| 源目录 | `<codex-skills-root>` |
| 当前会话现实 | `CODEX_HOME=<codex-home>` |
| 选择规则 | 仅同步名称匹配 `zzz-*` 的一级技能目录 |
| 目标仓库 | `<skills-repo-root>` |
| 调度器 | WSL 本机 `1Panel` 计划任务 `wsl-zzz-skills-sync` |
| 控制面仓库 | `<repo-root>` |

## Execution Entry

手动执行正式入口：

```bash
env -C <repo-root> agentplane infra automation apply wsl --name wsl-zzz-skills-sync --operation run --execute
```

只读核对计划任务对象：

```bash
env -C <repo-root> agentplane onepanel \
  --env wsl \
  cronjob search \
  --info wsl-zzz-skills-sync
```

## Expected Results

- `ok_no_changes`
  - 源目录与目标仓库内容一致，无需提交和推送
- `ok_pushed`
  - 检测到变化，已完成 `git add`、`git commit`、`git push`
- `failed_precheck`
  - 源目录缺失、目标仓库不在 `main`、工作树不干净、根目录存在不允许的未知文件，或本地分支落后于 `origin/main`
- `failed_runtime`
  - 文件复制、Git 提交或推送过程中失败

## 1Panel Task Baseline

- 任务 ID：`1`
- 任务名：`wsl-zzz-skills-sync`
- 周期：每 2 小时一次
- Cron：`0 */2 * * *`
- 工作目录：`<repo-root>`
- 命令：`agentplane infra automation apply wsl --name wsl-zzz-skills-sync --operation run --execute`

## Verification

建议每次调整后执行最小验证：

```bash
env -C <repo-root> uv run python -m unittest \
  tests.test_zzz_skills_sync \
  tests.test_host_automation \
  tests.test_cli_entrypoints \
  tests.test_inventory_generation -v

env -C <repo-root> agentplane infra automation apply wsl --name wsl-zzz-skills-sync --operation run --execute
env -C <repo-root> agentplane onepanel --env wsl cronjob search --info wsl-zzz-skills-sync
```

## Common Failures

### Dirty Git Worktree

现象：

- 返回 `failed_precheck`
- `reason` 中包含 `dirty worktree`

处理：

```bash
cd <skills-repo-root> && git status --short
```

确认这些改动是否为人工保留内容。若需要继续自动同步，先人工提交、清理或移动这些改动，再重跑同步。

### Unsupported Root Entries

现象：

- 返回 `failed_precheck`
- `reason` 中包含 `unsupported root entries`

说明：

- 目标仓库根仅允许 `.git/`、`.gitignore`、`README.md` 和 `zzz-*` 技能目录

处理：

- 审核该文件是否应纳入 allowlist
- 若不应保留，先人工移除或迁移

### Remote Drift Or Push Failure

现象：

- 返回 `failed_precheck` 或 `failed_runtime`
- `reason` 中涉及 `origin/main` 或 `git push`

处理：

```bash
cd <skills-repo-root> && git fetch origin main && git status -sb
```

若本地落后远端，先人工 fast-forward 到最新远端状态，再重跑同步。不要让计划任务自动 rebase 或 merge。

### Missing Source Root

现象：

- 返回 `failed_precheck`
- `reason` 中包含 `source root does not exist`

处理：

```bash
ls -la <codex-skills-root>
```

确认 Windows 侧目录挂载正常，且 `zzz-*` 技能仍位于该目录下。

## 人工接力边界

- 本 runbook 的正式入口只有 `infra automation apply ... --operation run`；不要把页面点击、Git 手工操作脚本或兼容 helper 写成默认流程。
- 若 1Panel 任务对象丢失或参数漂移，正式修复入口应优先使用 `infra automation apply ... --operation reconcile`，必要时再落到 `agentplane onepanel --env wsl cronjob ...` 的低层对象能力。
- 历史实验步骤、临时补救记录、一次性迁移过程应归档到 `docs/archive/runbooks/...`，不要继续留在 active 主体。

## Manual Inspection

以下内容只能作为只读补充：

- 打开 WSL 本机 1Panel 面板查看计划任务和最近执行记录
- 如需进一步核对对象层状态，继续使用 `agentplane onepanel --env wsl cronjob ...`
