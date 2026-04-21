# Live Integration Gate

## 定位

`live integration gate` 是真实 WSL/SSH/Docker 验证入口，不属于默认本地门禁。
默认 `pytest` 只验证 CLI、runbook 与边界合同；真实 live gate 必须显式执行。

## 硬边界

- 只在独立 Linux 文件系统 checkout 内执行，例如 `<linux-repo-root>`；`wsl` profile 还要求当前 shell 位于 WSL。
- 不允许从 Windows checkout、WSL UNC path 或 `/mnt/<drive>/...` 执行。
- 每个 checkout 只使用自己的 `.venv`。
- 不设置 `UV_PROJECT_ENVIRONMENT`，不创建 `.venv-win` 或 `.venv-wsl`。
- Windows 可以作为控制面入口，但 live gate 的实际执行目录必须是 Linux native checkout。

## 默认门禁

默认本地门禁继续只跑无现场依赖的测试：

```bash
uv run python -m pytest
uv run python -m agentplane.cli --help
```

`pyproject.toml` 默认排除这些真实现场标记：

- `live_gate`
- `integration_wsl`
- `integration_remote`
- `docker_required`
- `ssh_required`
- `external_app`

## 计划入口

计划入口可以在任意控制面 checkout 生成，不触碰现场：

```bash
uv run python -m agentplane.cli host live-gate plan --profile wsl --repo-root <repo-root>
uv run python -m agentplane.cli host live-gate plan --profile prod0-main --repo-root <repo-root>
```

`plan` 输出会列出每一步命令、所需能力与被阻断的 checkout 类型。

## 执行入口

执行入口只能在 Linux 文件系统 checkout 中运行：

```bash
cd <linux-repo-root>
uv run python -m agentplane.cli host live-gate run --profile wsl --repo-root <linux-repo-root> --execute
uv run python -m agentplane.cli host live-gate run --profile prod0-main --repo-root <linux-repo-root> --execute
```

`wsl` profile 覆盖：

- `uv`、Docker daemon、Docker Compose 基线。
- `host inventory wsl`。
- `host audit wsl`。
- `projection verification run --target wsl --profile wsl-fixture`。
- `app object verify --target wsl --app <app>`。
- `app delivery verify --target wsl --app <app> --execute`。

`prod0-main` / `prod2-main` profile 覆盖：

- SSH 可达性。
- 远端 Docker daemon 基线。
- `app object verify --target <target> --app <app>`。
- `app delivery verify --target <target> --app <app> --execute`。

## 结果处理

- 任一步失败即停止，返回已执行步骤的结构化结果。
- live gate 失败不应通过修改默认 `pytest` 门禁掩盖。
- 如果现场缺少 Docker、SSH、secrets 或应用仓库，直接记录阻塞原因；不要把真实现场验证混回默认门禁。
