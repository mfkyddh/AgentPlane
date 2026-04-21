# AgentPlane

`AgentPlane` 是一个 Agent-first control plane template repository。它把正式控制面的真源、resolver / backend 执行合同、runbook、skills 和 tracked projections 收口在同一个模板仓库里，供你 fork / clone 后交给 Agent 接管。

## 仓库定位

- `Git tracked truth + local secrets` 是正式真源模型。
- Windows / Linux / macOS 只在 `resolver / backend` 层分叉，不在 truth、runbook、skill 层分叉。
- 人类输入面只剩 `secrets` 和少量 `identity`；其余正式动作统一从 `uv run python -m agentplane.cli ...` 进入。
- 应用仓库只负责代码、构建资产、合同与非敏感模板；正式部署、验证、回写由控制面模板仓库负责。
- 本模板不再默认引用作者现场目录；所有示例统一使用 `<repo-root>`、`<target>`、`<app>` 之类占位符。
- Windows 与 WSL 禁止共享同一个工作目录；WSL 不能把 `/mnt/<drive>/...` 当成本仓库源码根。
- 每个物理 checkout 只保留一个项目虚拟环境：根目录 `.venv`。

## 当前现状

这份 README 既是模板入口，也反映当前仓库自己的运行现实：

- 当前控制面源码位于 Windows：`D:\Projects\AgentPlane`
- 当前 WSL 目标侧 live checkout 以 inventory 记录为准；它必须是独立 Linux 文件系统 checkout，不是 Windows 工作目录的 `/mnt/<drive>` 映射。
- 当前重点审查目标：`wsl`、`prod0-main`
- 当前应用层正式样板：`sub2api`

如果你要直接了解这份仓库在 `2026-04-14` 的真实状态、验证结果和待改造项，优先看：

- [current-state-and-validation.md](docs/runbooks/current-state-and-validation.md)

## 30 秒上手

1. `fork / clone` 本仓库，保留它作为你的正式控制面模板仓库。
2. 先确认本地入口：
   - Windows 宿主默认使用 `pwsh` 作为入口 shell。
   - Windows 宿主使用 `pwsh -NoProfile -ExecutionPolicy Bypass -File .\.codex\environments\lib\invoke-agentplane-windows-uv.ps1 python -m agentplane.cli ...`
   - Linux / macOS 直接使用 `uv run python -m agentplane.cli ...`
   - 不创建 `.venv-win`、`.venv-wsl`，也不把 WSL 工作目录指到 `/mnt/<drive>/<repo>`。
3. 检查当前宿主、工作区与 backend 绑定：
   `uv run python -m agentplane.cli bootstrap inspect-local --repo-root <repo-root>`
4. 生成本地 secrets 骨架：
   `uv run python -m agentplane.cli bootstrap init-secrets --repo-root <repo-root>`
5. 只填写 Agent takeover 必需的 truth：
   - `secrets/local/control-plane/...`
   - `secrets/targets/<target>/...`
   - `secrets/ssh/config`
   - `secrets/ssh/keys/*.pem`
6. 校验 readiness：
   `uv run python -m agentplane.cli bootstrap verify-secrets --repo-root <repo-root>`
7. 汇总是否满足接管条件：
   `uv run python -m agentplane.cli bootstrap doctor --repo-root <repo-root>`
8. 让 Agent 接管后续 domain 动作，不再默认引用作者现场目录。

## 正式入口

- 统一入口：`uv run python -m agentplane.cli <domain> <action> [flags]`
- Windows 宿主入口：`pwsh -NoProfile -ExecutionPolicy Bypass -File .\.codex\environments\lib\invoke-agentplane-windows-uv.ps1 python -m agentplane.cli <domain> <action> [flags]`
- 命令发现：`uv run python -m agentplane.cli --help`
- 常用仓库自检：`bash agentplane/scripts/internal/repo/self_check.sh`
- 虚拟环境：只使用当前 checkout 根目录的 `.venv`。

按 domain 进入正式任务：

- `host`：主机 identity、inventory、audit、cleanup、automation、network、remote、host secrets。
- `service`：受管运行服务对象与非 HTTP runtime attachments。
- `website`：公网入口对象与 `website publish` 工作流。
- `app`：catalog object、app resource、app delivery。
- `projection`：`runtime-env`、`verification`、`fixture`、`ledger`。
- `onepanel`：只保留 provider/debug 对象面：`panel`、`firewall`、`cronjob`、`task`。

常用模板化示例：

- `uv run python -m agentplane.cli host inventory <target> --repo-root <repo-root>`
- `uv run python -m agentplane.cli service verify --target <target> --name <service> --repo-root <repo-root>`
- `uv run python -m agentplane.cli website publish plan --target <target> --config-file <file> --cloudflare-env-file <file> --repo-root <repo-root>`
- `uv run python -m agentplane.cli app delivery validate-contract --target <target> --app <app> --repo-root <repo-root>`
- `uv run python -m agentplane.cli projection ledger refresh --target <target> --repo-root <repo-root> --write`

## 真源与执行模型

- tracked truth 放在 Git 内：`docs/`、`inventory/`、`infra/compose/`、`templates/`、`agentplane/`。
- 本地真实 secrets 只放在 `secrets/`，其中 `secrets/local/control-plane/` 与 `secrets/targets/<target>/` 是模板 bootstrap 的正式输入面。
- `resolver / backend` 负责把 canonical refs 解析到宿主或远端执行现场；Windows / Linux / macOS 的差异只允许留在这里。
- `plan -> apply -> verify -> ledger -> inventory -> doc-sync` 是正式执行闭环。

## 文档入口

### Core Contracts

- [control-plane.md](docs/architecture/control-plane.md)
- [linux-governance.md](docs/architecture/linux-governance.md)
- [agentplane-app-collaboration.md](docs/architecture/agentplane-app-collaboration.md)

### Active Runbooks

- [current-state-and-validation.md](docs/runbooks/current-state-and-validation.md)
- [bootstrap-secrets.md](docs/runbooks/bootstrap-secrets.md)
- [wsl-host-governance.md](docs/runbooks/wsl-host-governance.md)
- [prod0-main-governance.md](docs/runbooks/prod0-main-governance.md)
- [control-plane-agent-execution-flow.md](docs/runbooks/control-plane-agent-execution-flow.md)
- [control-plane-domain-onboarding.md](docs/runbooks/control-plane-domain-onboarding.md)
- [app-project-delivery-workflow.md](docs/runbooks/app-project-delivery-workflow.md)
- [onepanel-cli-validation-workflow.md](docs/runbooks/onepanel-cli-validation-workflow.md)

### Reference / History / Archive

- [app-repository-standard.md](docs/reference/app-repository-standard.md)
- [compat-retirement-ledger.md](docs/reference/compat-retirement-ledger.md)
- [control-plane-naming-registry.md](docs/reference/control-plane-naming-registry.md)
- [docs/history/index.md](docs/history/index.md)
- [docs/archive/README.md](docs/archive/README.md)

## 目录导航

- `.codex/`：环境动作、repo-owned skills 与自动化入口。
- `docs/`：长期合同、active runbook、reference、history、archive。
- `inventory/`：tracked objects、server summaries 和 projections。
- `infra/compose/`：服务 compose 资产与模板。
- `agentplane/`：Python CLI、resolver / backend runtime、内部脚本。
- `templates/`：非敏感模板。
- `secrets/`：本地敏感 truth，默认不提交。
