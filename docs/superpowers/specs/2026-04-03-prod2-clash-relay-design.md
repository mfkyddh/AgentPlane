# Prod2 Clash Relay Design

**Date:** 2026-04-03

## Goal

为 `prod2-main` 新增一套可供 Windows `Clash Nyanpasu` 直接消费的远端中继方案，满足以下目标：

- 保留现有 Windows `Remote Profile`
- 新建一套完整复制当前规则体系的 `prod2` profile
- 在 `prod2-main` 上提供正式的 `Trojan + TLS` 远端节点
- 使用 `relay.zzzai.fun:24443`
- `relay.zzzai.fun` 由 Cloudflare 管理，但以灰云直连 `prod2-main`
- 方案必须融入 `OP_Linux` 现有 `host / service / inventory / secrets / runbook` 框架，而不是仓库外的一次性脚本

已确认前提：

- 目标主机：`prod2-main`
- 公网地址：`38.12.32.94`
- SSH 端口：`44222`
- 云厂商：朝晞云
- 区域：美国洛杉矶
- 目标协议：`Trojan + TLS`
- 目标域名：`relay.zzzai.fun`
- 目标端口：`24443/tcp`
- Cloudflare DNS 由本仓库实施流程负责

## Scope

本轮纳入：

- `prod2-main` 上新增正式 relay runtime service
- 设计该 service 在仓库中的对象归属、文件布局、secret 边界、inventory 表达方式
- 设计 `relay.zzzai.fun` 的 Cloudflare DNS 灰云接入方式
- 设计 Windows 侧新 `prod2` profile 的派生策略
- 设计最小可操作的验证闭环与回滚口径
- 设计 runbook / inventory / spec / plan 落点

本轮不纳入：

- 把非 HTTP/TLS 协议入口硬塞进 `website publish`
- 修改现有 `prod2-main` 上 `1panel.zzzai.fun`、`token.zzzai.fun`、`newapi.zzzai.fun`、`vmail.zzzai.fun` 的公网入口逻辑
- 直接覆盖用户当前 Windows `clash-config.yaml`
- 设计多协议并存方案，例如 `Hysteria2`、`VLESS`、`VMess`
- 在本轮扩张到通用 “任意协议公网端点对象” 的全仓库抽象

## Current Context

当前事实：

- `prod2-main` 的 `80/443` 已由 `1panel-openresty-prod` 占用，承载现有 HTTP/HTTPS 公网入口。
- `prod2-main` 的正式公网 website 仍按 `website publish` 语义治理，真源在 `inventory.services.public_websites` 与相关 runbook。
- 仓库的正式运行服务对象通过 `service` 域表达；tracked runtime service 既可以是固定对象，也可以是 inventory 中声明的 `compose` / `onepanel-app` / `onepanel-compose` service。
- 仓库已有 Cloudflare 管理口径，正式输入文件为 `secrets/env/prod-jump.env`。
- Windows `Clash Nyanpasu` 当前使用单一 `clash-config.yaml`，规则直接挂在各 `proxy-groups` 上，没有现成的第二套 `Remote Profile` 真源模型。

这意味着：

1. 新 relay 不能复用现有 `80/443`，否则会把非 HTTP 协议与现有公网 website 耦合。
2. 新 relay 不应表达为 `website`，因为它不是网站，也不应走 `website publish`。
3. Windows profile 应视为客户端派生配置，服务真源必须留在仓库与远端受管资产中。

## Boundary

| 域 | 管什么 | 不管什么 |
| --- | --- | --- |
| `host` | `prod2-main` 的网络前置条件、云安全组/主机防火墙、远端运行环境 | profile 规则编排 |
| `service` | `relay_trojan` 运行服务对象、监听端口、运行状态、计划与核验 | Cloudflare 网站发布、Windows GUI 切换 |
| `website` | 现有 HTTP/HTTPS 网站入口 | `Trojan` 这类非 HTTP 协议入口 |
| `secrets/hosts` | relay 密码、证书申请参数、host-first 真源 | tracked compose 目录 |
| `secrets/services` | relay 兼容投影 env | 真源职责定义 |
| `inventory` | `relay_trojan` 服务事实与公网协议端点摘要 | 客户端 profile 文件本体 |
| Windows derived profile | 基于现有 `clash-config.yaml` 派生出的 `prod2` profile | 远端服务真源、Cloudflare truth |

## Decision

本轮采用以下设计决策：

1. 在 `prod2-main` 上新增正式服务对象 `relay_trojan`。
2. 运行形态优先采用仓库现有模式的 `compose` service，目录落在 `infra/compose/relay-trojan/`。
3. 运行数据落在 `/data/relay-trojan/`。
4. 公网入口固定为 `relay.zzzai.fun:24443`，协议为 `Trojan + TLS`。
5. `relay.zzzai.fun` 在 Cloudflare 中使用灰云；Cloudflare 只负责 DNS 事实管理，不承担协议转发。
6. `relay_trojan` 不作为 `website` 对象；它是 `service` 自带的 public protocol endpoint。
7. 证书签发采用 `DNS-01`，避免改动现有 `80/443` 入口。
8. Windows 侧不覆盖现有 profile；新建一份完整复制当前规则体系的 `prod2` profile。
9. 新 profile 只替换节点集合，不重写原规则与分组拓扑。

## Service Model

建议 service 名称：`relay_trojan`

建议 inventory 表达要点：

- `control_plane`: `compose`
- `container_name`: `relay-trojan-prod`
- `runtime_root`: `/data/relay-trojan`
- `config_files`: remote env / config 路径
- `host_binding`: `0.0.0.0:24443`
- `container_port`: `24443`
- `public_endpoint`:
  - `domain`: `relay.zzzai.fun`
  - `port`: `24443`
  - `protocol`: `trojan`
  - `transport`: `tcp+tls`
  - `cloudflare_proxy`: `false`
- `certificate_mode`: `Cloudflare DNS-01`

这样收口后，`service get/verify` 的对象语言仍然成立，而不会误导为一个普通网站。

## Repository Layout

建议新增或修改以下文件：

```text
infra/compose/relay-trojan/
  docker-compose.prod2.yml
  config.template.json
  README.md

secrets/hosts/prod2-main/relay-trojan/
  service.env
  dns01.env
  windows-profile.meta.env

secrets/services/
  relay-trojan.prod2.env

inventory/servers/prod2-main/
  inventory.json
  README.md

docs/runbooks/
  prod2-main-relay-trojan.md

docs/superpowers/specs/
  2026-04-03-prod2-clash-relay-design.md
```

说明：

- `secrets/hosts/prod2-main/relay-trojan/*` 是真源。
- `secrets/services/relay-trojan.prod2.env` 仅作为 runtime / compose compatibility projection。
- Windows 真实配置文件仍在用户主机目录；仓库内只保留模板、说明或生成规则。

## Cloudflare Model

Cloudflare 在本方案中只承担 DNS 管理，不承担代理转发。

目标记录：

- `type=A`
- `name=relay.zzzai.fun`
- `content=38.12.32.94`
- `proxied=false`

为什么不走橙云：

- 标准 Cloudflare 代理并不为本方案承担通用 `Trojan` 透传语义。
- 当前需求是稳定复用 `Clash` 远端节点，不是通过 HTTP 网站入口伪装代理。
- 灰云可让证书、端口和握手问题的排障路径更短。

## Windows Profile Strategy

Windows 侧采取“完整复制、独立切换”的策略：

1. 读取当前 `C:\Users\Administrator\AppData\Roaming\Clash Nyanpasu\config\clash-config.yaml`
2. 保留原 `rules`
3. 保留原 `proxy-groups` 名称与分组结构
4. 生成新的 `prod2` profile 文件
5. 新 profile 中的节点集合只包含 `relay_trojan` 对应的 `Trojan` 节点定义
6. 旧 profile 原样保留，不做覆盖

这样做的目的：

- 降低切换成本
- 保持现有分流习惯
- 让问题定位限定在“新节点链路”而不是“规则改写”

## Network And Security

前置条件：

- 朝晞云放行 `24443/tcp`
- 主机防火墙允许 `24443/tcp`

端口选择依据：

- 避开现有 `80/443/44222`
- 避免与当前 website / 1Panel / SSH 语义冲突
- 让 `Trojan` 监听与现有公网服务边界清晰

密钥与凭据要求：

- Trojan password 必须由真源 secret 驱动
- TLS 证书不得与 `1panel.zzzai.fun` 现有 website 证书混用
- 所有 secret 文件按仓库既有规范保持 `600`

## Verification

必须具备的验证闭环：

### Remote Service

- `ss -ltnp` 确认 `24443` 正在监听
- 容器或服务日志确认 `Trojan` 进程正常启动
- 配置文件与投影 env 一致

### DNS / TLS

- `relay.zzzai.fun` 解析到 `38.12.32.94`
- Cloudflare 记录为灰云
- `openssl s_client -connect relay.zzzai.fun:24443 -servername relay.zzzai.fun` 返回正确证书链与域名

### Clash Client

- 新 profile 可被 `Clash Nyanpasu` 正常加载
- `GPT`、`国外流量` 等关键组能够通过新节点转发
- 切换到新 profile 时不影响旧 profile 的可用性

### Repository Truth

- `inventory`、runbook、spec、模板、secret 路径说明一致
- 如本轮把 `relay_trojan` 接入正式 `service` 面，则至少具备最小 `service verify` 口径

## Rollback

回滚策略必须保持简单：

1. Windows 侧切回旧 profile
2. Cloudflare 删除或停用 `relay.zzzai.fun` 记录
3. 停止 `relay_trojan` 服务
4. 保留仓库内 spec / runbook / inventory 历史，不做伪删除

因为旧 profile 全程保留，客户端回滚应是秒级的。

## Risks

### 风险 1：把非 HTTP 入口硬塞进 `website`

这会污染现有 `website publish` 语义，并让仓库对象边界倒退。

控制方式：明确 `relay_trojan` 只属于 `service`，其公网端点作为 service 附带事实记录。

### 风险 2：Windows profile 与服务真源倒挂

如果把 Windows `clash-config.yaml` 当真源，后续就无法通过仓库治理远端服务。

控制方式：把远端 service / DNS / secret / inventory 作为真源，Windows profile 只做派生。

### 风险 3：证书与现有 website 证书混用

这会扩大 `1panel-openresty-prod` 与新 relay 的耦合面。

控制方式：`relay.zzzai.fun` 使用独立 DNS-01 证书与独立运行服务。

### 风险 4：云安全组和主机防火墙口径不一致

仅打开其中一层会造成“DNS 正常但握手失败”的假象。

控制方式：把朝晞云放行和主机防火墙检查都写入 runbook 与验证步骤。

## Success Criteria

当以下条件同时满足时，本方案认为设计达成：

- `prod2-main` 上新增 `relay_trojan` 正式受管运行服务对象
- `relay.zzzai.fun:24443` 可作为 `Trojan + TLS` 节点稳定连接
- Cloudflare DNS 记录由正式流程管理，且保持灰云
- 旧 Windows profile 原样保留
- 新 `prod2` profile 完整复制当前规则体系，仅替换节点集合
- 仓库内 `service / inventory / secrets / runbook` 边界明确，不把 relay 伪装成 `website`
- 回滚路径清晰且不依赖临时手工记忆
