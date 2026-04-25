---
status: active
owner: AgentPlane maintainers
last_verified: 2026-04-25
superseded_by: null
audience: both

---

# 🧪 Live Integration Gate

结论：live gate 是真实 WSL/SSH/Docker 验证入口，必须显式 `--execute`，不混入默认本地门禁。

## 📌 定位

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
agentplane --help
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
agentplane infra live-gate plan --profile wsl --repo-root <repo-root>
agentplane infra live-gate plan --profile prod0-main --repo-root <repo-root>
```

`plan` 输出会列出每一步命令、所需能力与单 checkout 执行策略。

## 执行入口

执行入口使用当前 checkout 运行：

```bash
agentplane infra live-gate run --profile wsl --repo-root <repo-root> --execute
agentplane infra live-gate run --profile prod0-main --repo-root <repo-root> --execute
```

`wsl` profile 覆盖：

- `uv`、Docker daemon、Docker Compose 基线。
- `infra inventory wsl`。
- `infra audit wsl`。
- `projection verification run --target wsl --profile wsl-fixture`。
- `projection runtime-env verify --target wsl --app <app>`。
- `service verify --target wsl --name <app>`。

`prod0-main` / `prod2-main` profile 覆盖：

- SSH 可达性。
- 远端 Docker daemon 基线。
- `projection runtime-env verify --target <target> --app <app>`。
- `service verify --target <target> --name <app>`。

## 结果处理

- 任一步失败即停止，返回已执行步骤的结构化结果。
- live gate 失败不应通过修改默认 `pytest` 门禁掩盖。
- 如果现场缺少 Docker、SSH、secrets 或受管服务，直接记录阻塞原因；不要把真实现场验证混回默认门禁。
- 当前 active live gate 不再依赖本地应用仓库 catalog；从源码交付的应用重新 onboard 后再进入 `app delivery` 门禁。
