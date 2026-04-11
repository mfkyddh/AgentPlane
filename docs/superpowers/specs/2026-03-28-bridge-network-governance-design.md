# Managed Bridge Network Governance Design

**Date:** 2026-03-28

## Goal

为 `OP_Linux` 增加一套通用的受管 Docker bridge 网络治理能力，能够：

- 用结构化 inventory 声明生产主机需要的 bridge 网络
- 审计网络对象、bridge 接口、宿主机网关地址与路由
- 在控制面命令中按需自动修复缺失状态
- 把这套治理前移到新机器纳管和应用部署前置步骤中，避免再次出现“容器健康但宿主机与公网不可达”的故障

## Incident Summary

`prod2-main` 本次 `sub2api` 上线时，`sub2api-prod` 容器内部 `127.0.0.1:8080/health` 正常，Docker network `zqf_network` 也仍然存在，但宿主机侧 bridge 接口 `br-66f7da1be943` 丢失了 `172.19.0.1/16` 地址与对应路由。

结果是：

- 宿主机无法访问 `172.19.0.0/16` 网段内的容器 IP
- `127.0.0.1:18080 -> 172.19.0.3:8080` 的 DNAT 虽存在，但宿主机无法真正走通
- OpenResty 反代和公网入口一起失效

现有治理只覆盖“容器必须挂载 `zqf_network`”，没有覆盖“宿主机必须能访问该 bridge 网络”，因此故障未被提前拦截。

## Scope

本设计覆盖：

- `OP_Linux` 控制面 CLI
- `inventory/servers/<target>/inventory.json` 的结构化声明
- 部署前与巡检时的 bridge 网络审计/修复
- 新机器纳管与 runbook 文档

本设计不覆盖：

- 在目标机上安装常驻 systemd 自愈单元
- 自动修改未声明的第三方 Docker 网络
- 通过容器内业务健康检查替代网络层校验

## High-Level Approach

新增一个独立的 `ops.cli network` 命令族，专门治理受管 Docker bridge 网络。每个目标环境在 inventory 中显式声明其受管网络，包括：

- `name`
- `driver`
- `subnet`
- `gateway_ip`
- `required_for`

控制面只对这些显式声明的网络执行审计与修复，不扫描和改写其他 Docker 网络。

`ops.cli network` 提供两个核心动作：

- `audit`：读取 inventory 声明并检查 live 状态
- `ensure`：在 `audit` 基础上，对缺失的 network、bridge 地址、路由做最小修复

然后把 `ensure` 接入：

- `ops.cli app deploy --execute`
- `ops.cli app verify --execute`
- 新机器治理/纳管 runbook

## Inventory Contract

在 `inventory/servers/<target>/inventory.json` 新增顶层字段：

```json
{
  "managed_bridge_networks": [
    {
      "name": "zqf_network",
      "driver": "bridge",
      "subnet": "172.19.0.0/16",
      "gateway_ip": "172.19.0.1/16",
      "required_for": [
        "postgres18-prod",
        "redis7-prod",
        "minio-prod",
        "sub2api-prod"
      ]
    }
  ]
}
```

约束：

- `driver` 当前仅支持 `bridge`
- `gateway_ip` 必须是带前缀长度的 CIDR 形式
- `required_for` 仅做可读性与台账说明，不作为修复目标枚举器

## CLI Design

新增：

```bash
uv run python -m ops.cli network audit --target prod2-main --repo-root /root/work/OP_Linux
uv run python -m ops.cli network ensure --target prod2-main --repo-root /root/work/OP_Linux
```

### `network audit`

输出内容：

- 目标环境
- 每个受管网络的声明值
- live Docker network 是否存在
- driver 是否匹配
- Docker network 返回的 subnet / gateway
- bridge 接口名是否能从 network inspect 推导出来
- 宿主机 bridge 接口是否存在
- 宿主机是否持有 `gateway_ip`
- 宿主机是否有对应子网路由
- `ok: true/false`

### `network ensure`

修复顺序：

1. 若 network 不存在，按声明创建 network
2. 若 network 存在但 driver 不是 `bridge`，直接报错，不做危险修复
3. 若 bridge 接口存在但缺失 `gateway_ip`，执行 `ip addr add <gateway_ip> dev <bridge_if>`
4. 若路由缺失，执行 `ip route replace <subnet> dev <bridge_if> src <gateway_ip_without_prefix>`
5. 修复后重新做一次 audit，并把最终状态写回返回 payload

不做的事：

- 不删除重建已有 network
- 不修改未声明网络
- 不尝试处理 overlay/macvlan 等其他 driver

## Deployment Integration

在 `ops.cli app deploy --execute` 和 `ops.cli app verify --execute` 前置调用 `network ensure`：

- 目标为生产环境时才触发
- 只针对当前 target 的 `managed_bridge_networks`
- 若 ensure 失败，则 deploy/verify 失败退出

这样做的意义：

- 新机器首次切应用前，会先补齐受管 bridge 网络
- 老机器 drift 后，再次部署或校验时也能自动兜底

## New-Host Prevention

新机器纳管流程中必须新增一条固定步骤：

```bash
uv run python -m ops.cli network ensure --target <prod0-main|prod2-main|...> --repo-root /root/work/OP_Linux
```

并要求在 runbook 中明确说明：

- “容器挂载了 `zqf_network`” 不等于宿主机可达
- 任何正式部署前都必须执行或隐式触发 `network ensure`
- inventory 中不声明的 bridge 网络不会被控制面修复

## Testing Strategy

测试覆盖分三层：

1. 单元测试
   - 解析 inventory 中的 `managed_bridge_networks`
   - audit 对缺失 network / 缺失 gateway / 缺失 route 的判定
   - ensure 生成的远端命令顺序
2. 集成型 CLI 测试
   - `ops.cli network audit`
   - `ops.cli network ensure`
3. 接入回归测试
   - `ops.cli app deploy --execute` 在生产 target 上先执行 network ensure
   - `ops.cli app verify --execute` 在生产 target 上先执行 network ensure

## Files To Change

- `ops/cli/app.py`
- `ops/cli/apps.py`
- `ops/cli/audit.py`
- `ops/cli/inventory.py`
- `ops/cli/networks.py`（new）
- `tests/test_app_cli.py`
- `tests/test_prod0_audit.py`
- `inventory/servers/prod2-main/inventory.json`
- `inventory/servers/prod2-main/README.md`
- `docs/runbooks/app-project-delivery-workflow.md`
- `docs/runbooks/prod2-main-1panel-public-access.md`

## Rollout Notes

- `prod2-main` 会先作为第一批采用者，把 `zqf_network` 纳入 `managed_bridge_networks`
- 后续新机器只要 inventory 提前写好受管网络声明，就能直接复用同一套治理命令
- 这次事故会以“bridge gateway drift”形式写入 `prod2-main` 的 README/inventory notes
