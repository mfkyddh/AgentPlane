---
status: active
owner: AgentPlane maintainers
last_verified: 2026-05-01
superseded_by: null
audience: both
layer: project
---

# 1Panel 更新适配与扩展规划

结论：AgentPlane 不应把 1Panel 复刻成第二个面板，而应把 1Panel 当成 provider substrate。每次 1Panel 更新后，先做 provider 合同差异识别，再把高频用户任务收口到 `infra`、`service`、`ingress`、`app`、`projection` 等正式对象面。

---

## 范围

本文服务 [主线追踪器](backlog.md) 中的分支任务 B1：1Panel 最新适配与扩展功能规划。

本文回答三个问题：

1. 1Panel 更新后，AgentPlane 如何快速同步与适配。
2. 基于 1Panel 的哪些能力应优先扩展到 AgentPlane。
3. 如何避免功能扩展破坏 [控制面合同](../architecture/control-plane.md)。

不在本文范围内：

- 不新增 raw `onepanel container / website / app / database` 公开入口。
- 不定义 1Panel UI 克隆路线。
- 不承诺一次性覆盖 1Panel 全部 API。

---

## 当前事实

### 上游快照

| 项 | 当前值 |
|----|--------|
| 本地源码 | `D:\Projects\00GITHUB\1Panel` |
| 分支 | `dev-v2...origin/dev-v2` |
| 最新提交 | `a5a5d9f1ac4adc318dbfff50aa848418b155ac69` |
| 提交时间 | `2026-04-29 09:41:53 +0000` |
| 提交说明 | `fix: adjust container log download timeout (#12632)` |

### 1Panel v2 路由密度

| 路由组 | 路由数 | 对 AgentPlane 的含义 |
|--------|--------|----------------------|
| `containers` | 73 | `service`、`app delivery`、容器证据与运行态对账 |
| `websites` | 67 | `ingress`、站点发布、HTTPS、反代与域名对账 |
| `hosts` | 57 | `infra`、防火墙、SSH、监控、磁盘与主机事实 |
| `databases` | 54 | `app resource`、数据资源、secret 投影与权限对账 |
| `apps` | 31 | `app object`、安装应用、参数、升级与 compose 模板 |
| `runtimes` | 31 | PHP/Node 运行时事实，暂不作为首批主线 |
| `settings` | 26 | 面板配置与备份快照，需谨慎接入 |
| `cronjobs` | 16 | `infra automation`、备份、续期、清理任务 |
| `websites/ssl` | 13 | `ingress` HTTPS 证书对账 |
| `openresty` | 10 | `ingress` provider 运行态与 reload 证据 |
| `ai/files/toolbox/alert/dashboard` | 多个 | 后续能力池，首批不优先 |

### AgentPlane 当前边界

- `onepanel` 是隐藏的 provider/debug 入口，只保留 `panel`、`firewall`、`cronjob`、`task`。
- 正式用户入口是 `infra`、`service`、`ingress`、`app`、`projection`。
- 所有正式操作必须遵循 plan -> execute -> verify -> record。
- 1Panel endpoint、raw id、面板参数名不能泄漏成长期公开合同。

---

## 适配机制

### 目标

每次 1Panel 更新后，AgentPlane 应能在一个短周期内回答：

- 1Panel 哪些 route、request、response、行为发生变化。
- 这些变化影响哪些 AgentPlane 正式对象面。
- 是否需要改 provider adapter、fixture、Skill、文档或测试。
- 是否可以安全升级生产目标，还是需要冻结 provider 版本。

### 标准流程

| 步骤 | 动作 | 产物 | 通过条件 |
|------|------|------|----------|
| 1 | 更新本地 1Panel 源码快照 | commit、branch、路由清单 | 能追溯到明确提交 |
| 2 | 生成 provider route fingerprint | route group、method、path、handler | 与上一版可 diff |
| 3 | 分类差异 | added、removed、renamed、payload-changed、behavior-changed | 每个差异归属到正式对象面 |
| 4 | 跑 provider 合同测试 | fake fixture、object API shape、error code | 不破坏现有正式输出合同 |
| 5 | 跑目标域测试 | `infra`、`service`、`ingress`、`app`、`projection` 最小测试 | 高风险域通过 |
| 6 | 必要时跑 live gate | WSL 或显式目标环境 | 只读核验先行 |
| 7 | 更新记录 | backlog、文档、变更说明 | 可审计、可回滚 |

### 差异分类

| 类型 | 例子 | 处理方式 |
|------|------|----------|
| Route 新增 | 新的 `/websites/*` 或 `/containers/*` 能力 | 先记录能力池，不自动公开 |
| Route 删除或重命名 | 旧 adapter 调用路径失效 | provider adapter 兼容修复，补回归测试 |
| Request 字段变化 | install、firewall、cronjob payload 调整 | adapter 内部映射，正式 CLI 参数不变 |
| Response 形状变化 | search/list 返回分页结构变化 | object normalizer 修复，ledger shape 不变 |
| 行为变化 | apply 变成异步 task | formal surface 增加 task verify 或 operation evidence |
| 鉴权/签名变化 | header、token、timestamp 规则调整 | `providers` 层修复，不影响业务域 |
| 路径/存储变化 | compose、网站、证书目录变化 | runtime resolution 或 inventory 投影修复 |

### 建议新增的适配资产

| 资产 | 作用 | 建议位置 |
|------|------|----------|
| provider snapshot manifest | 记录 1Panel commit 与 route fingerprint | `inventory` 或 `tmp` 生成物，先不提交生产敏感信息 |
| route diff checker | 更新后快速定位 API 面变化 | `agentplane repo` 或维护者脚本，最终由 CLI 包装 |
| object API contract fixtures | 覆盖 1Panel response shape | `tests/onepanel` |
| domain impact matrix | route group -> AgentPlane domain 映射 | 本文或后续 reference 文档 |
| live compatibility checklist | WSL/prod 只读核验清单 | `docs/runbooks` 或 Skill downstream docs |

### 更新节奏

- 日常：不追每个 upstream commit，只跟踪本地镜像当前 commit。
- 小更新：route fingerprint 无变化时，只跑 provider 合同测试和 fast gate。
- 中更新：route 或 payload 变化时，先修 adapter，再评估正式对象面是否扩展。
- 大更新：鉴权、task、目录结构或核心 API 大改时，冻结生产升级，先做 WSL live gate。

---

## 扩展原则

1. 从用户最常见任务出发，而不是从 1Panel API 数量出发。
2. 优先只读核验，再做 plan/apply。
3. 正式对象面必须有稳定标识：`target`、`app_id`、`service name`、`ingress alias`。
4. 1Panel raw id 只能作为 evidence 或 provider 内部字段。
5. 所有 mutate 操作必须能解释预期变化、执行证据和验证结果。
6. Secrets 只引用逻辑路径，不在文档、ledger 或 stdout 中泄漏值。

---

## 用户任务优先级

目标用户是个人开发者、小团队、开源维护者、自托管服务维护者。最常见的问题通常是：

| 优先级 | 用户问题 | AgentPlane 对象面 |
|--------|----------|-------------------|
| P0 | 我现在有哪些服务在跑，是否健康 | `service search/get/verify` |
| P0 | 我的网站是否在线，HTTPS 是否正确 | `ingress search/get/verify` |
| P0 | 有没有多暴露端口 | `infra network/firewall audit` |
| P0 | 备份、证书续期、清理任务是否存在并成功 | `infra automation search/get/verify` |
| P1 | 我能否安全重启、更新、回滚一个服务 | `service plan/apply`、`app delivery` |
| P1 | 应用依赖的数据库和 Redis 是否绑定正确 | `app resource verify` |
| P2 | 我能否从 1Panel 应用商店纳管常用应用 | `app object`、`app delivery` |
| P2 | 我想看趋势、告警和资源瓶颈 | `infra audit`、后续 observability |
| P3 | 我想管理文件、进程、工具箱和 AI 面板能力 | 暂不进入首批 |

---

## 功能扩展路线

### 第一批：高频只读核验

| 能力 | 上游 1Panel 面 | 正式入口 | 首个可交付 |
|------|----------------|----------|------------|
| 容器/Compose 运行态对账 | `containers` | `service` | inventory 声明服务与 live container 状态差异 |
| 网站与 HTTPS 对账 | `websites`、`websites/ssl`、`openresty` | `ingress` | alias/domain/HTTPS/origin 状态核验 |
| 防火墙漂移检查 | `hosts/firewall/*` | `infra network` 或 `infra firewall` | 声明公网入口与实际开放端口比对 |
| 定时任务健康 | `cronjobs` | `infra automation` | 备份、续期、清理任务存在性与最近执行结果 |
| 数据资源声明核验 | `databases` | `app resource` | app 资源声明、secret scope、live 数据库摘要一致 |

### 第二批：受控 plan/apply

| 能力 | 正式入口 | 说明 |
|------|----------|------|
| 服务 restart/reconcile | `service plan/apply` | 只允许 inventory 中声明的 managed service |
| 网站 publish/reconcile | `ingress publish/plan/apply` | 继续用配置文件作为外部输入 |
| 防火墙 allow/deny | `infra network plan/apply` | 只围绕声明端口和 ingress/service endpoint |
| 定时任务启停/更新 | `infra automation plan/apply` | 先覆盖备份、证书续期、清理任务 |
| app resource provision | `app resource plan/apply` | 优先数据库、Redis、MinIO bucket 等常用依赖 |

### 第三批：应用与运行时

| 能力 | 正式入口 | 说明 |
|------|----------|------|
| 1Panel installed app 纳管 | `app object` | 识别已安装应用，映射为 catalog object |
| 1Panel app install 计划 | `app delivery` | 仅用于常用模板，不暴露 raw install 参数 |
| PHP/Node runtime 核验 | `service` 或 `app delivery` | 只在真实 app 交付需要时接入 |
| 数据库用户和权限轮转 | `app resource` | 必须先完成 secrets lifecycle 设计 |

### 暂缓能力

| 上游面 | 暂缓原因 |
|--------|----------|
| `files` | 容易变成文件管理器克隆，且权限风险高 |
| `ai` | 与 AgentPlane 当前主线无直接关系 |
| `toolbox/process` | 更适合故障排查专项，不应先公开 |
| `settings/snapshot` | 涉及备份、恢复、面板级风险，需单独威胁建模 |
| `dashboard/alert` | 可做 evidence，但不是首批闭环能力 |

---

## 建议实施里程碑

### M0：规划落地

- 建立本文。
- 在 backlog 中保持 B1 可追踪。
- 明确不扩大 raw `onepanel` 公开面。

### M1：Provider 更新门禁

- 已实现首个 route fingerprint 命令：`agentplane repo provider onepanel route-fingerprint --source-root <1panel-source-root> --repo-root <repo-root>`。
- 支持 `--baseline` 与 `--fail-on-drift`，可作为后续更新漂移门禁。
- 已建立 route diff -> AgentPlane surface impact matrix：输出 `impact_matrix`、`impact_summary`，drift 结果输出 `impact` 摘要。
- 为 `object_api.py` 现有关键 helper 增加 contract fixture。
- 将更新检查纳入 `repo health-check` 或维护者命令。

### M2：只读能力扩展

- 扩展 `service verify` 对容器和 compose live 证据的覆盖。
- 扩展 `ingress verify` 对网站、域名、HTTPS、OpenResty reload 状态的覆盖。
- 扩展 `infra automation verify` 对 cronjob 最近执行记录的覆盖。
- 扩展 `infra network audit` 对 1Panel firewall rule 的只读对账。

### M3：可变更能力扩展

- 为防火墙、定时任务、ingress reconcile 提供 plan/apply。
- 每个 apply 都记录 operation ledger。
- 每个 apply 后必须触发 verify。

### M4：App resource 与 1Panel 应用纳管

- 将数据库、Redis、MinIO 等常见资源纳入 `app resource`。
- 对已安装 1Panel app 做只读 catalog mapping。
- 只在合同成熟后开放 app install/update plan。

### M5：观测与告警

- 将 dashboard、alert、monitor 信息作为 evidence 接入。
- 不直接复刻监控 UI。
- 优先输出适合 Agent 判断的结构化健康摘要。

---

## 验收标准

每个新增 1Panel 适配或扩展能力都必须满足：

| 类别 | 标准 |
|------|------|
| 合同 | 正式 CLI 输出字段稳定，provider 细节不外泄 |
| 测试 | unit/fake fixture 覆盖 response shape，必要时有 live gate |
| 文档 | 更新相关 Skill、runbook 或 reference；说明无需更新也要写明 |
| 安全 | 不输出 secret 值；mutate 操作必须 plan 先行 |
| 记录 | apply 后写 operation ledger，状态变化可追溯 |
| 回滚 | 失败时给出可执行的 rollback 或人工处理建议 |

---

## 风险与对策

| 风险 | 对策 |
|------|------|
| 1Panel route 高频变化导致 adapter 易碎 | 用 route fingerprint 和 fixture 提前发现 |
| 功能扩展变成面板克隆 | 坚持正式对象面和用户任务优先 |
| raw id 泄漏成长期合同 | 所有 raw id 只保留在 evidence/provider payload |
| mutate 操作误伤生产 | plan/apply 分离，默认只读，live gate 显式开启 |
| 文件、备份、恢复能力风险高 | 暂缓，先做威胁建模和恢复演练 |
| 文档与 Skill 不同步 | 新能力验收时强制检查 Skill catalog 和 downstream docs |

---

## 下一步建议

1. 先实现 M1：Provider 更新门禁。
2. 再实现 M2 的四个只读面：容器运行态、网站 HTTPS、防火墙漂移、定时任务健康。
3. 等只读 evidence 稳定后，再开放 M3 的 plan/apply。
4. 数据库和 1Panel app install 放到 M4，避免过早扩大写面。
