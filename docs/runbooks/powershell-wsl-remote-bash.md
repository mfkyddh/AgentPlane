# PowerShell WSL Remote Bash Runbook

## Purpose

定义“当前 shell 不在 WSL”时的补充入口，避免 `$()`、`$var`、CRLF 与多层引号在本地 shell 被提前解释，导致远端命令失真。默认工作流仍然是先进入 WSL，再执行仓库里的 Linux 命令。

## Failure Modes This Runbook Prevents

- PowerShell 把 `$(date ...)` 解释成 `Get-Date`
- `wsl.exe -e bash -lc 'ssh ... "..."'` 中的 `$var`、`$(...)` 被本地 Bash 提前展开
- PowerShell here-string 把 `\r\n` 送进 WSL，远端 Bash 读到带 `\r` 的路径或变量
- 多层 `\"`、`'\"'\"'` 嵌套后 SQL、awk、sed 片段截断

## Stable Rule

- PowerShell 只负责把参数送入 WSL，不负责拼最终远端 shell 文本。
- 优先 `wsl.exe -u root -e <program> <args...>`；只有 WSL 内确实需要 shell 特性时才退回 `sh -lc` / `bash -lc`。
- 正式远端 Bash 入口统一为 `uv run python -m agentplane.cli host remote bash ...`。
- `agentplane/scripts/internal/` 下脚本只作为仓库内部实现与示例，属于兼容层，不再作为长期主命令面。
- `agentplane/scripts/onepanel/api_request.py`、`app_lifecycle.py`、`project_lifecycle.py` 这类 compat helper 仅用于 compat、troubleshooting 与 provider/debug 低层核对，不进入 active execution path。
- Formal catalog apps with `schema_version: 1` must use `uv run python -m agentplane.cli app object ...`, `app delivery ...`, `service ...`, and `website ...`; lower-level helper surfaces are not the active execution path.
- 从 Windows PowerShell 发起远端多语句 Bash 时，优先把脚本保存成 Linux 路径文件；stdin 只推荐在纯 Linux shell 内使用。

## Official CLI

仓库正式入口：

```bash
uv run python -m agentplane.cli host remote bash <target> [--repo-root <linux-path>] [--script-file <linux-path>] [--dry-run] [-- <arg>...]
```

默认工作流：

```bash
cd /root/work/AgentPlane
uv run python -m agentplane.cli host remote bash prod0-main \
  --script-file /root/work/AgentPlane/agentplane/scripts/internal/remote/example.sh
```

如果当前 shell 仍在宿主机侧，再使用补充入口：

```bash
wsl.exe -u root -e env -C /root/work/AgentPlane \
  uv run python -m agentplane.cli host remote bash prod0-main \
  --script-file /root/work/AgentPlane/agentplane/scripts/internal/remote/example.sh
```

行为：

- 自动解析仓库 SSH 配置与目标别名
- 在 worktree 中也会回溯主仓库 `secrets/ssh/config`
- 通过 `ssh -T ... "bash -s -- ..."` 把脚本体送到远端 Bash
- 对生产非 root 目标自动补 `sudo`
- `--dry-run` 输出结构化执行计划
- `--` 之后的参数会变成远端脚本的 `$1..$N`

## Recommended Patterns

先判断当前是否已经在 WSL：

- 已在 WSL：直接执行本仓库文档里的 Linux 命令。
- 不在 WSL：用本 runbook 的补充入口把参数送进 WSL，再交给正式 CLI。

### 1. PowerShell 发起远端多语句脚本

先准备 Linux 脚本文件：

```bash
#!/usr/bin/env bash
set -euo pipefail
echo "host=$(hostname)"
docker ps --format 'table {{.Names}}\t{{.Status}}' | sed -n '1,10p'
```

再执行：

```bash
wsl.exe -u root -e env -C /root/work/AgentPlane \
  uv run python -m agentplane.cli host remote bash prod0-main \
  --script-file /root/work/AgentPlane/agentplane/scripts/internal/remote/example.sh
```

### 2. 纯 Linux shell 内部直接 pipe

只在已经进入 WSL/Linux shell 时使用：

```bash
printf '%s\n' \
  'set -euo pipefail' \
  'echo "host=$(hostname)"' \
  'id' \
| uv run python -m agentplane.cli host remote bash prod0-main
```

### 3. 远端脚本参数

本地：

```bash
wsl.exe -u root -e env -C /root/work/AgentPlane \
  uv run python -m agentplane.cli host remote bash prod0-main \
  --script-file /root/work/AgentPlane/agentplane/scripts/internal/remote/example-arg.sh \
  -- postgres18-prod
```

远端脚本：

```bash
#!/usr/bin/env bash
set -euo pipefail
container_name="$1"
docker inspect "$container_name" --format '{{.Name}} {{.State.Status}}'
```

## Anti-Patterns

不要这样写：

```bash
wsl.exe -u root -e sh -lc 'ssh prod0-main "ts=$(date +%Y%m%d%H%M%S); echo $ts"'
```

问题：

- `$(date ...)` 和 `$ts` 可能先被本地 Bash 展开
- 一旦命令从 PowerShell 拼进来，还可能先被 PowerShell 二次解释

不要这样写：

```powershell
@'
set -euo pipefail
echo hi
'@ | wsl.exe -u root -e bash -s
```

问题：

- PowerShell here-string 默认带 CRLF，Bash 可能读到尾随 `\r`

## Verification

验证包装脚本和 SSH helper：

```bash
wsl.exe -u root -e env -C /root/work/AgentPlane \
  uv run pytest tests/test_ssh_targets.py tests/test_cli_entrypoints.py tests/test_remote_cli.py -q
```

最小 dry-run 验证：

```bash
wsl.exe -u root -e env -C /root/work/AgentPlane \
  uv run python -m agentplane.cli host remote bash prod0-main \
  --dry-run \
  --script-file /root/work/AgentPlane/agentplane/scripts/internal/remote/example.sh
```

最小远端连通性验证：

```bash
wsl.exe -u root -e sh -lc 'cd /root/work/AgentPlane && printf "%s\n" "set -euo pipefail" "echo remote_ok" | uv run python -m agentplane.cli host remote bash prod0-main'
```

## Cutover Guidance

- 对数据库切换、证书切换、OpenResty 切换这类需要多语句远端脚本的任务，先把脚本落成 Linux 文件，再执行。
- 在 Windows PowerShell 中，不要拼 `ssh ... bash -lc ...`；应改成 `wsl.exe -e env -C ... uv run python -m agentplane.cli host remote bash ... --script-file ...`
- 不要在 PowerShell 里直接内联 SQL、awk、sed、`docker exec ... psql -c "..."` 这类多层引用命令。
- 如果脚本内容需要复用或审计，优先放到 `agentplane/scripts/internal/remote/`；一次性脚本可放到受控的 Linux 临时路径，再通过 CLI 执行。

