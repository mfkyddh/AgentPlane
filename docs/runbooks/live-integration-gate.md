# Live Integration Gate

## 定位

`live integration gate` 是真实 WSL/SSH/Docker 验证入口，不属于默认本地门禁。
默认 `pytest` 只验证 CLI、runbook 与边界合同；真实 live gate 必须显式执行。

## 硬边界

- 只使用当前单 checkout；不要为了 live gate 再复制一份源码。
- Windows 宿主可以执行 `wsl` profile；正式 `agentplane.cli` 步骤仍在 Windows host 入口执行，只有 Linux-only 工具链探针通过 WSL backend 访问同一工作树。
- 每个 checkout 只使用自己的 `.venv`。
- 不设置 `UV_PROJECT_ENVIRONMENT`，不创建 `.venv-win` 或 `.venv-wsl`。
- 默认本地门禁仍不执行真实 WSL/SSH/Docker；live gate 必须显式加 `--execute`。

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

`plan` 输出会列出每一步命令、所需能力与单 checkout 执行策略。

## 执行入口

执行入口使用当前 checkout 运行：

```bash
uv run python -m agentplane.cli host live-gate run --profile wsl --repo-root <repo-root> --execute
uv run python -m agentplane.cli host live-gate run --profile prod0-main --repo-root <repo-root> --execute
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
- `app object verify` 与 `app delivery verify` 需要 catalog 指向的应用仓库合同文件真实存在；缺少应用仓库 checkout 时，live gate 应直接失败并记录缺口。
