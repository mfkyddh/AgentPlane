# WSL Host Governance Runbook

## Purpose

统一 WSL 本地环境的运维治理检查步骤，确保后续自动化执行基线一致。

## Formal Host Truth Vocabulary

- WSL 主机治理现在使用与 `prod0-main`、`prod2-main` 一致的主机真值词汇：`host`、`service`、`container`、`website`、`firewall`、`cronjob`、`app_resource`、`automation` 等，每个对象都要在 `inventory/servers/wsl/inventory.json` 以及 `ledgers/` 目录写入快照。
- 任何正式场景的变更必须同时在 runbook 与 ledger 中描述，确保 CLI 中 `uv run python -m agentplane.cli host ...` 输出的主机快照与文档保持同步。
- 只要在本地执行 `uv run python -m agentplane.cli host inventory wsl --repo-root /root/work/AgentPlane`，就能拿到和 `prod0-main`/`prod2-main` 同等级的主机真值视图，避免再以“本地 baseline”描述治理内容。

## Preconditions

- 当前仓库路径：`/root/work/AgentPlane`
- 已按 [bootstrap-secrets.md](bootstrap-secrets.md) 完成本地 secrets 初始化
- 具备 Docker 与 SSH 基础可用性
- 当前会话已经进入 WSL shell；本 runbook 中的命令直接在这里执行

## 1. Verify Execution Identity

```bash
whoami
printf "%s\n" "$HOME" "$PWD"
```

预期：

- 用户为 `root`
- `HOME` 为 `/root`
- 仓库路径可解析到 `/root/work/AgentPlane`

## 2. Verify Toolchain Baseline

```bash
uv --version
python3 --version
docker --version
docker compose version
```

预期：

- `uv`、`python3`、`docker`、`docker compose` 均可执行

## 3. Verify Secrets Permissions

```bash
env -C /root/work/AgentPlane ls -ld secrets secrets/env secrets/ssh secrets/ssh/keys secrets/services
env -C /root/work/AgentPlane sh -lc 'ls -l secrets/ssh/config secrets/env/prod-jump.env secrets/ssh/keys/*.pem'
```

预期：

- 目录权限符合最小暴露原则
- `config`、`env`、`pem` 等敏感文件非宽权限

## 4. Verify WSL Network Baseline

```bash
ip route | awk '/default/ {print $3}'
```

说明：

- 需要访问宿主机代理时，优先使用当前网关 IP，而非 `127.0.0.1`/`localhost`。
- WSL 虽然是本地主机，但网络判断照搬生产模式：所有临时代理、网桥、端口映射都应该遵循主机真值的网络定位，而不是直接绕过 `mihomo` 或 `docker` 网桥。

## 5. Verify Unified CLI Entry

```bash
env -C /root/work/AgentPlane uv run python -m agentplane.cli --help
env -C /root/work/AgentPlane uv run python -m agentplane.cli host audit wsl --repo-root /root/work/AgentPlane
env -C /root/work/AgentPlane uv run python -m agentplane.cli host inventory wsl --repo-root /root/work/AgentPlane
```

说明：

- WSL 本机治理统一从 `uv run python -m agentplane.cli host ...` 进入。
- `host` 的公开动作、跨域边界与正式任务入口以 [control-plane.md](../architecture/control-plane.md) 为准，不在本 runbook 复制维护。
- WSL 的 `agentplane.cli host inventory`/`host audit` 输出就是本地主机真值的起点，执行后要把当日快照保存在 `inventory/servers/wsl/ledgers/*.json` 里以对齐生产目标的 ledger 规范。
- WSL 的写回顺序固定为：先执行 `uv run python -m agentplane.cli host inventory wsl --repo-root /root/work/AgentPlane --write` 刷新 `inventory/servers/wsl/inventory.json` 根快照，再执行 `uv run python -m agentplane.cli projection ledger refresh --target wsl --repo-root /root/work/AgentPlane --write` 刷新 `object_ledgers` 与 `ledgers/*.json|md`；`verification-*.json|md` 只允许由 `uv run python -m agentplane.cli projection verification run --target wsl --profile wsl-fixture --repo-root /root/work/AgentPlane --write-report` 生成。
- 若当前 shell 不是 WSL，会先进入 WSL，再执行这些同样的 Linux 命令。
- 若返回 `No module named agentplane.cli`，说明该分支尚未完成 CLI 入口落地，需先补齐对应实现。

## 6. Verify Host Truth Ledgers

- `inventory/servers/wsl/inventory.json` 及其 `object_ledgers` 字段记录正式的主机、服务、容器、网站、自动化、cronjob、应用与 app resource 等统计，刷新后要确保 ledger 中的 `counts` 与 `ledgers/*.json` 内容一致，保持和 `prod0-main`、`prod2-main` 同样的概念边界。
- 变更服务、容器或自动化任务时，先运行 `uv run python -m agentplane.cli host inventory wsl --repo-root /root/work/AgentPlane` 再更新对应的 ledger 文件，如 `inventory/servers/wsl/ledgers/containers.json`，形成可追溯的主机真值更新链路。
- 本 runbook 与 [`docs/runbooks/prod0-main-governance.md`](prod0-main-governance.md)、[`docs/runbooks/prod2-main-1panel-public-access.md`](prod2-main-1panel-public-access.md) 共同定义了主机真值语料，新增条目时同步更新 runbook、inventory 和 ledger，避免在不同主机之间用不同的术语。

## 7. Governance Notes

- WSL 本机 `1Panel` 计划任务只负责调度，不在页面中承载业务逻辑。
- 本机计划任务必须通过 `uv run python -m agentplane.cli host ...` 或对应专题正式入口调用仓库内控制面，所有算作主机真值的自动化都要同时写入 `inventory/servers/wsl/ledgers/automations.json`，且文档、inventory 和 ledger 保持一致。
- 新增本机计划任务时，必须同步更新 `inventory/servers/wsl/inventory.json`、对应 runbook 与验证命令，以在主机真值上下文中形成闭环。
- `secrets/` 目录的加密远端备份统一由 `wsl-agentplane-secrets-backup` 负责，运行说明见 [wsl-secrets-backup.md](wsl-secrets-backup.md)。
- 生产专题变更请走对应专题 runbook；本文件仅定义 WSL 基线治理步骤，术语和目标与生产 runbook 保持一致，不再使用“local baseline”或“临时标配”的独立语义。
