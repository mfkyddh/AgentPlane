# prod0-main Governance Runbook

## 目标

统一 `prod0-main` 的目录、配置、证书、入口和运行控制面，避免生产资产继续散落在 `/opt`、`/etc`、`/var/lib` 与临时目录。

## 当前正式口径

- 主控制面：`1Panel`
- 应用运行控制面：`AgentPlane compose`
- 主数据根目录：`/data`
- 正式公网入口：`1panel-openresty-prod:8443`
- 正式证书目录：`/data/1panel/www/certs/`
- 公开站点对象：`1panel`、`newapi`、`pay`、`token`
- 宿主级代理控制面：`mihomo.service`

## 目录合同

- 1Panel：`/data/1panel/**`
- Redis：`/data/redis/data`
- PostgreSQL：`/data/postgres/data`
- MinIO：`/data/minio/{data,config}`
- Mihomo：`/etc/mihomo/**`（当前仍为宿主级配置目录，未收口到 `/data`）
- NewAPI：由 AgentPlane `compose` 管理，容器接入 `zqf_network`
- `sub2api`：目标目录 `"/data/sub2api/{data,config,logs}"`
- `sub2apipay`：目标目录 `"/data/sub2apipay/{data,config,logs}"`

## 审计与 Inventory

- `inventory/servers/prod0-main/inventory.json` 及其 `object_ledgers` 是 prod0-main 主机的唯一仓库级快照。所有其它文档段落和 CLI/测试输出都应以它的字段为依据，防止出现“prod0-main 是特殊 undocumented case” 的状况。`object_ledgers` 字段内的 `websites`、`containers`、`firewall` 等条目应随着 `uv run python -m agentplane.cli host inventory prod0-main --repo-root /root/work/AgentPlane` 的执行而刷新。
- `uv run python -m agentplane.cli host inventory prod0-main --repo-root /root/work/AgentPlane` 当前是 tracked inventory readback，不是 live collector；它负责读出并在需要时回写已跟踪的 `inventory.json`，不会像 WSL 那样重新扫描本机 Docker/路径。
- 审计侧表层同样从 `inventory/servers/prod0-main/ledgers` 目录读取具体项：`ledgers/websites.json`、`ledgers/containers.json`、`ledgers/firewall.json` 等文件必须与 runbook 中描述的路径/端口保持一致。`uv run python -m agentplane.cli host audit prod0-main --repo-root /root/work/AgentPlane` 在检查注册表时会对照这些 ledgers 并生成可追踪的 `ledgers` 元数据。
- `uv run python -m agentplane.cli projection ledger refresh --target prod0-main --repo-root /root/work/AgentPlane --write` 只刷新 `object_ledgers`、`ledgers/*.json|md` 与目标 README，不负责生成 `verification-prod0-*.json|md`；验证报告只能通过 `projection verification run --write-report` 生成。
- 相关测试（例如 `tests/test_repo_snapshot_contracts.py` 以及 `tests/test_docs_no_legacy_terms.py`）依赖这份资料来证明 `prod0-main` 并非一个未认证的特殊机房入口；本节中列出的命令和目录必须与这些测试中硬编码的路径/文件同步。

## 治理要求

- 网站必须先存在为 1Panel 网站对象，再计为正式上线。
- OpenResty 维持 `host` 网络，其余项目容器默认接入 `zqf_network`。
- 远端运行时 env 只允许作为 `secrets/` 或 1Panel 投影副本存在，不允许新增散落副本。
- `mihomo.service` 属于 `prod0-main` 的正式宿主基础设施，不再按“临时代理工具”处理；凡是影响 Docker 网桥、宿主出站代理或代理探测链路的变更，都要把它纳入同一变更窗口。
- 当前 `mihomo` 为 `sub2api` 的 `clash` 代理记录和部分 OpenAI/ChatGPT 出站流量提供宿主 mixed proxy 入口；默认监听目标是 `172.18.0.1:7890`，控制器是 `127.0.0.1:19090`。
- 任何宿主机重启、Docker 网络重建、`mihomo` 配置变更后，都必须复核 `systemctl status mihomo`、`systemctl show -p After,Requires mihomo` 与 `ss -ltnp | grep 7890`。
- `inventory/servers/prod0-main/README.md` 属于可再生成摘要，不承担事故细节留档；宿主治理类事件要写入本 runbook 或同级 runbook。
- `minio-prod` 上的正式应用用户必须绑定各自的 bucket-scoped policy，不允许继续保留内置全局 `readwrite`。
- `inventory/servers/prod0-main/app-resources.json` 与 `inventory.json` 记录 MinIO 的 `bucket`、`access_key`、`policy_name`、`policy_scope`、`isolation_level` 非敏感元数据。
- 历史迁移端口、历史入口组件、旧证书同步脚本都不再属于正式交付范围。

## Secrets 归档

- `prod0-main` 的主机级 secrets 以 `secrets/hosts/prod0-main/` 为最终规范（若目录尚未初始化，变更前请先创建再赋予合适的权限），服务级 env 文件继续居于 `secrets/services/`，典型条目有 `secrets/services/onepanel-api.env`、`secrets/services/sub2api.prod0.env`、`secrets/services/sub2apipay.prod0.env`，它们在 inventory 的 `services` 字段（`api_env_local`）以及 `app_resource_summary` 中（`secret_file`）被明确引用，避免出现 undocumented 的 secrets 位置漂移。
- 更细粒度的应用资源凭据应写入 `secrets/hosts/prod0-main/apps/<app>/resources/`，并在 `inventory/servers/prod0-main/app-resources.json` 中以 bucket/policy/isolation 等字段记录，只保留非敏感元数据，确保 `tests/test_app_onboarding_standard.py` 与 `tests/test_repo_snapshot_contracts.py` 能可靠验收这一层。
- 运行时验证可以使用 `env -C /root/work/AgentPlane ls -l secrets/services/onepanel-api.env secrets/services/sub2api.prod0.env secrets/services/sub2apipay.prod0.env` 来确认服务 env 已同步；`uv run python -m agentplane.cli host secrets prod0-main --repo-root /root/work/AgentPlane` （若命令可用）则补充检查 host-first secrets 入口。

## 网络与代理

- `zqf_network` 是 prod0-main 上除 1Panel 以外所有容器的默认 bridge，inventory 中 `managed_bridge_networks` 字段记录 driver、subnet `172.18.0.0/16`、gateway `172.18.0.1/16` 及强依赖容器。任何 Docker network 变更都应用 `docker network inspect zqf_network` 与 `inventory` 中保持一致。
- 混合代理由 `mihomo.service` 提供，必须维持与 `docker.service` 的 `Requires`/`After` 依赖（`systemctl show -p After,Requires mihomo` 里必须包含 `docker.service`），`ss -ltnp | grep 7890` 显示 `172.18.0.1:7890` 由 Mihomo 监听；`uv run python -m agentplane.cli host network audit prod0-main --repo-root /root/work/AgentPlane` 用于 CLI 侧确认代理出口与路由表的稳定性。
- 正式公网入口由 `1panel-openresty-prod`（`host` 网络模式）统一承载 8443 端口，inventory 的 `security.openresty_public_listen` 与 `services.onepanel_openresty` 均含端口、双栈与证书信息。`ss -ltnp | grep ':8443'` 加上 `uv run python -m agentplane.cli host audit prod0-main --repo-root /root/work/AgentPlane` 可以联动检查 OpenResty + Cloudflare 公网链路。

## 1Panel 升级预检口径

- `2026-03-30` 通过仓库 CLI 实测，`prod0-main` 当前 live 1Panel 版本是 `v2.1.6`。
- 本轮 CLI-first 控制面与 runbook 主要按 `v2.1.7` 基线沉淀，因此 `prod0-readonly` 的角色是升级前预检，不是同版本验收。
- 当前 `prod0-readonly ok=yes` 只表示 `panel`、`firewall`、`task` 这些只读面仍可读取且与当前仓库 CLI 兼容，不表示主机已经完成 `v2.1.7` 升级。
- `inventory/servers/prod0-main/ledgers/verification-prod0-readonly.json|md` 是 `projection verification run --target prod0-main --profile prod0-readonly --repo-root /root/work/AgentPlane --write-report` 生成的机器报告；解释性口径以本 runbook 和主机 README 为准。

## 核对命令

### 远端状态与网络

```bash
cd /root/work/AgentPlane
uv run python -m agentplane.cli host remote bash prod0-main --dry-run --script-file /root/work/AgentPlane/agentplane/scripts/internal/remote/example.sh
printf '%s\n' 'set -euo pipefail' 'docker ps --format '"'"'{{.Names}}|{{.Status}}|{{.Ports}}'"'"'' \
  | uv run python -m agentplane.cli host remote bash prod0-main
printf '%s\n' 'set -euo pipefail' "ss -ltnp | grep ':8443'" \
  | uv run python -m agentplane.cli host remote bash prod0-main
printf '%s\n' 'set -euo pipefail' 'systemctl status mihomo --no-pager -l | sed -n '"'"'1,40p'"'"'' \
  | uv run python -m agentplane.cli host remote bash prod0-main
printf '%s\n' 'set -euo pipefail' 'systemctl show -p After,Requires mihomo --no-pager' \
  | uv run python -m agentplane.cli host remote bash prod0-main
printf '%s\n' 'set -euo pipefail' "ss -ltnp | grep 7890" \
  | uv run python -m agentplane.cli host remote bash prod0-main
```

### 审计与 Inventory CLI

```bash
cd /root/work/AgentPlane
uv run python -m agentplane.cli host inventory prod0-main
uv run python -m agentplane.cli host audit prod0-main
```

### 网络审计

```bash
cd /root/work/AgentPlane
uv run python -m agentplane.cli host network audit prod0-main --repo-root /root/work/AgentPlane
```

### Secrets 验证

```bash
env -C /root/work/AgentPlane ls -l secrets/services/onepanel-api.env secrets/services/sub2api.prod0.env secrets/services/sub2apipay.prod0.env
```

### 投影与 Ledger

```bash
cd /root/work/AgentPlane
uv run python -m agentplane.cli projection verification run --target prod0-main --profile prod0-readonly --repo-root /root/work/AgentPlane --write-report
uv run python -m agentplane.cli projection ledger refresh --target prod0-main --repo-root /root/work/AgentPlane --write
```

`onepanel panel|firewall|task` 仅是 provider/debug 补充读取，不是 `prod0-main` 预检主入口。

## 迁移说明

- `sub2api` 当前正式运行已由 AgentPlane `compose` 承接，不再保留旧 `systemd` 回滚入口。
- `sub2apipay` 已在 `2026-03-30` 切换到 AgentPlane `compose`，不再把旧 `systemd` unit 登记为正式回滚入口。
- `mihomo.service` 当前仍保留宿主级 systemd 形态，因为它需要与 Docker 网桥地址 `172.18.0.1` 协同工作；`2026-03-27` 已增加 `/etc/systemd/system/mihomo.service.d/docker-order.conf`，要求 `Requires=docker.service` 且 `After=docker.service`，避免宿主重启后 mixed proxy 监听在 Docker 网桥未就绪时启动失败。
- 历史收口讨论归档参考：`docs/archive/runbooks/prod0-main-sub2-control-plane-convergence.md`；当前正式决策仍以 `inventory/servers/prod0-main/`、本 runbook 与 `uv run python -m agentplane.cli ...` 为准。

## 2026-03-27 Mihomo 启动顺序事故

现象：

- `sub2api` 后台 IP 管理中名称为 `clash` 的代理测试连接失败。
- `sub2api-prod` 日志报 `proxyconnect tcp: dial tcp 172.18.0.1:7890: connect: connection refused`。

根因：

- `mihomo` 使用 `bind-address: 172.18.0.1`，mixed proxy 目标监听是 `172.18.0.1:7890`。
- 主机在 `2026-03-27` 重启时，`mihomo` 先于 `docker.service` 拉起，Docker 网桥地址尚未就绪。
- 启动日志报 `listen tcp 172.18.0.1:7890: bind: cannot assign requested address`，导致服务进程存活但 7890 未监听。

现场修复：

- 重启 `mihomo.service`，待 Docker 网桥存在后恢复 `172.18.0.1:7890` 监听。
- 增加 systemd drop-in：`/etc/systemd/system/mihomo.service.d/docker-order.conf`

```ini
[Unit]
Requires=docker.service
After=docker.service
```

验收结论：

- `systemctl show -p After,Requires mihomo` 已包含 `docker.service`。
- `ss -ltnp | grep 7890` 已恢复 `mihomo` 监听 `172.18.0.1:7890`。
- 从 `sub2api-prod` 容器内通过该代理访问 `ip-api` 成功。
- 之后若账号测试返回上游 `401 token_invalidated`，应按账号令牌失效处理，而不是回退判断为宿主代理故障。
