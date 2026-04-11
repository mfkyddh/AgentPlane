# Host Automation Formal Entry Design

**Date:** 2026-04-02

## Goal

删除顶层 `automation`，把 WSL 本机自动化任务收口到唯一正式入口 `uv run python -m ops.cli host automation ...`，同时保留它们在 1Panel 面板计划任务中的可见性和可管理性。

## Background

基于当前工作区实际状态，现有顶层 `automation` 只有 3 类能力：

1. `sync-zzz-skills`
2. `backup-secrets-r2`
3. `ensure-secrets-backup-cronjob`

它们都不构成独立一级对象域：

- 真正的任务对象都发生在 `wsl` 主机上
- 调度器是 `1Panel cronjob`
- `inventory/servers/wsl/inventory.json` 已经把它们登记在 `automations[]`
- 仓库已存在低层 `onepanel cronjob` 对象面，足以承担控制器对象读写

因此更合理的边界不是继续保留顶层 `automation`，也不是把这些任务硬塞进 `onepanel`，而是：

- `host automation` 负责“任务面”
- `onepanel cronjob` 负责“调度器对象面”

## Scope

本轮只做：

1. 删除顶层 `automation` parser 与 dispatch。
2. 新增 `host automation search/get/verify/plan/apply`。
3. 把 `inventory/servers/wsl/inventory.json` 中的 `automations[]` 作为声明真源。
4. 把 1Panel 计划任务脚本统一切到 `host automation apply ... --operation run --execute`。
5. 把 active 文档、skills、帮助输出与测试切到新入口。

本轮不做：

1. 不新建单独的 `automation` 对象域。
2. 不把 `onepanel cronjob` 从低层对象面提升成默认任务面。
3. 不支持 `wsl` 之外的新 automation target。
4. 不扩展新的 automation task，只覆盖当前 inventory 中已声明的两类任务。

## Decision

采用“task 面并入 `host`，controller 保持在 `onepanel cronjob`”方案。

### Why not keep top-level `automation`

- 语义过散，像杂项桶
- 当前动作都绑定 `wsl`
- 不利于继续压缩顶层 CLI

### Why not move everything to `onepanel cronjob`

- 这会把正式入口退化成控制器对象 API
- 用户需要直接面对 `id`、`mode`、`body-json`
- “任务是什么”和“调度器对象长什么样”会混在一起

### Chosen shape

任务面：

```bash
uv run python -m ops.cli host automation search wsl --repo-root /root/work/OP_Linux
uv run python -m ops.cli host automation get wsl --name wsl-zzz-skills-sync --repo-root /root/work/OP_Linux
uv run python -m ops.cli host automation verify wsl --name wsl-op-linux-secrets-backup --repo-root /root/work/OP_Linux
uv run python -m ops.cli host automation plan wsl --name wsl-op-linux-secrets-backup --operation reconcile --repo-root /root/work/OP_Linux
uv run python -m ops.cli host automation apply wsl --name wsl-op-linux-secrets-backup --operation reconcile --execute --repo-root /root/work/OP_Linux
```

控制器对象面：

```bash
uv run python -m ops.cli onepanel --env wsl cronjob search --info wsl-op-linux-secrets-backup
uv run python -m ops.cli onepanel --env wsl cronjob get --id 2
```

## Operations

`host automation` 本轮最小支持 3 类操作：

1. `run`
   - 执行任务本体
   - 供 1Panel cronjob 定时触发
2. `reconcile`
   - 创建或更新 1Panel cronjob，使其与 inventory 声明一致
3. `trigger`
   - 通过 1Panel cronjob 对象执行一次手动触发

## Source Of Truth

本轮声明真源固定为 `inventory/servers/wsl/inventory.json` 的 `automations[]`。

每条 automation 至少提供：

- `name`
- `controller`
- `spec`
- `cwd`
- `command`

其中：

- `command` 表示任务本体的正式运行命令
- 1Panel cronjob 的 `script` 由 `cd <cwd> && <command>` 生成

## Output Contract

`host automation` 统一采用 `host` envelope：

```json
{
  "command": "host",
  "action": "automation.verify",
  "target": "wsl",
  "payload": {}
}
```

`payload` 内最小字段：

- `search` -> `items`
- `get` -> `automation`
- `verify` -> `ok`、`checks`、`automation`、`live`
- `plan` -> `ok`、`operation`、`automation`、`actions`
- `apply` -> `ok`、`operation`、`automation`、`actions`

## Verification

最小验证：

```bash
uv run python -m pytest \
  tests/test_cli_entrypoints.py \
  tests/test_host_cli.py \
  tests/test_host_automation.py \
  tests/test_docs_no_legacy_terms.py -q

uv run python -m ops.cli --help
uv run python -m ops.cli host --help
uv run python -m ops.cli host automation --help
```
