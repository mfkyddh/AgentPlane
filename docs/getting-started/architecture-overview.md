---
status: active
owner: AgentPlane maintainers
last_verified: 2026-04-30
superseded_by: null
audience: human
---

# 🏗️ AgentPlane 架构概览

结论：AgentPlane 的核心是"三层投影"体系——从 Git 配置和现场状态派生出机器可消费的只读视图，支撑对账、审计和回写。理解投影模型，就理解了 AgentPlane 的设计哲学。

---

## 🎯 一句话理解 AgentPlane

```
人类说目标 → AI 匹配 Skill → CLI 执行操作 → 验证结果 → 写回投影
```

AgentPlane 不直接操作服务器，而是通过**标准化入口**操作，每一步都留下**可追溯的证据**。

---

## 🧱 核心架构：三层投影模型

### 什么是"投影"？

投影是从**真源**派生出的**只读视图**。就像数据库的视图一样，投影不存储原始数据，而是从真源计算得出。

**真源优先级**（从高到低）：
1. **Live State**（现场状态）— 服务器上实际运行的，优先级最高
2. **Inventory**（台账）— Git 中声明的受管对象
3. **Ledger**（证据）— 机器派生的验证记录
4. **Runbook**（文档）— 人类可读的说明

### 三层投影总览

```
┌─────────────────────────────────────────────────────────────┐
│                    第三层：App Summary                        │
│                    （人类可读摘要）                            │
│                    回答"当前正式口径是什么"                    │
└─────────────────────────────────────────────────────────────┘
                              ↑ 派生自
┌─────────────────────────────────────────────────────────────┐
│                    第二层：Object Ledgers                     │
│                    （机器派生证据）                            │
│                    回答"最近一次验证结果是什么"                │
└─────────────────────────────────────────────────────────────┘
                              ↑ 派生自
┌─────────────────────────────────────────────────────────────┐
│                    第一层：Host Inventory                     │
│                    （非敏感台账）                              │
│                    回答"该 target 有哪些受管对象"              │
└─────────────────────────────────────────────────────────────┘
                              ↑ 来源
┌─────────────────────────────────────────────────────────────┐
│                    真源：Git 配置 + Live State                │
│                    inventory.json + 现场命令/API              │
└─────────────────────────────────────────────────────────────┘
```

---

## 📊 第一层：Host Inventory（台账）

### 是什么？

目标环境的**正式非敏感台账**，回答："这个服务器上有哪些受管对象？它们的摘要状态是什么？"

### 存储位置

```
inventory/
├── servers/
│   └── prod0-main/
│       ├── inventory.json      # 结构化真源
│       └── README.md           # 人类可读摘要
└── apps/
    └── catalog.json            # 应用 catalog 索引
```

### inventory.json 结构

```json
{
  "label": "prod0-main",
  "provider": "tencent",
  "region": "ap-guangzhou",
  "public_ip": "xxx.xxx.xxx.xxx",
  "ssh": { "user": "root", "port": 22 },
  "security": { "firewall": { ... } },
  "services": {
    "redis": { "container_name": "redis7-prod", "status": "running" },
    "postgres": { "container_name": "postgres16-prod", "status": "running" },
    "sub2api": {
      "control_plane": "onepanel-compose",
      "container_name": "sub2api-prod",
      "app_resource_summary": { ... }
    },
    "public_ingresses": [ ... ]
  },
  "automations": [ ... ],
  "object_ledgers": {
    "generated_at": "2026-04-23T00:49:57.932935+00:00",
    "counts": { "websites": 2, "containers": 5, "apps": 1 },
    "ledgers": {
      "websites": "inventory/servers/prod0-main/ledgers/websites.json",
      "containers": "inventory/servers/prod0-main/ledgers/containers.json"
    }
  }
}
```

### 关键规则

- **只存非敏感信息**：密码、密钥、证书绝不进 inventory
- **逻辑路径优先**：只存 `apps/<app>` 这类平台无关路径，物理路径（Windows 盘符、WSL UNC）只在运行时解析
- **Minimum Key Model**：每个对象至少有 `target`, `kind`, `name_or_alias`, `source_of_truth`, `status`, `last_verified_at`, `evidence_refs`, `owned_by`

### 目前支持的对象类型

| 对象类型 | 说明 | 示例 |
|----------|------|------|
| **基础设施服务** | 数据库、缓存、对象存储 | redis, postgres, minio |
| **应用服务** | 业务应用容器 | sub2api |
| **公网入口** | 域名、证书、反向代理 | websites |
| **防火墙规则** | 端口、IP 白名单 | firewall |
| **定时任务** | cronjob、自动化任务 | cronjobs, automations |

### 如何刷新

```bash
# 更新主机 inventory
agentplane infra inventory prod0-main

# 查看 inventory
agentplane infra inventory prod0-main --json
```

---

## 📋 第二层：Object Ledgers（证据）

### 是什么？

围绕某类对象生成的**机器派生记录**，回答："最近一次验证结果是什么？证据来自哪里？"

### 存储位置

```
inventory/servers/prod0-main/ledgers/
├── websites.json          # 公网入口证据
├── websites.md            # 人类可读版本
├── containers.json        # 容器证据
├── containers.md
├── firewall.json          # 防火墙证据
├── firewall.md
├── cronjobs.json          # 定时任务证据
├── cronjobs.md
├── apps.json              # 应用证据
├── apps.md
├── app_resources.json     # 应用资源证据
├── app_resources.md
├── automations.json       # 自动化任务证据
├── automations.md
└── verification-default.json  # 验证套件结果
```

### 当前 7 种 Ledger 类型

| Ledger | 回答的问题 | 来源 |
|--------|-----------|------|
| **websites** | "有哪些公网入口？状态如何？" | `inventory.services.public_ingresses` |
| **containers** | "有哪些容器在运行？" | `inventory.services` 中有 `container_name` 的条目 |
| **firewall** | "防火墙规则是什么？" | `inventory.security.firewall` |
| **cronjobs** | "有哪些定时任务？" | `inventory.automations` 中 controller 含 cronjob |
| **apps** | "有哪些正式应用？" | `inventory/apps/catalog.json` |
| **app_resources** | "应用占用了哪些资源？" | `app-resources.json` |
| **automations** | "有哪些自动化任务？" | `inventory.automations` 全部条目 |

### JSON 结构示例

**containers.json**：
```json
{
  "items": [
    {
      "image": "redis:7.4.7",
      "container_name": "redis7-prod",
      "status": "running",
      "host_binding": "0.0.0.0:6379",
      "service_key": "redis",
      "last_cli_operation": {
        "action": "verify",
        "result": "verified",
        "timestamp": "2026-04-23T00:48:56.864599+00:00"
      }
    }
  ],
  "count": 5
}
```

**app_resources.json**：
```json
{
  "items": [
    {
      "owner_app": "sub2api",
      "ledger_status": {
        "intent": "live-db-partition-ledger",
        "runtime_credential_model": "shared-runtime-credentials",
        "tenant_isolation": "logical-db-partition-not-strong-isolation"
      },
      "postgres": { "database": "sub2api_prod0", "user": "sub2api_prod0" },
      "redis": { "db": 1, "key_prefix": "sub2api:" },
      "minio": { "bucket": "prod0-sub2api" },
      "secret_files": [
        "secrets/hosts/prod0-main/apps/sub2api/resources/postgres.env"
      ]
    }
  ],
  "count": 1
}
```

### 关键机制

**注解机制**：每个 ledger 行会自动附加 `last_cli_operation`，记录最近一次 CLI 操作（action/result/timestamp），形成操作证据链。

**字段过滤**：ledger 只保留"tracked fields"，过滤掉"observation-only fields"（如 `resolved_path`, `contract_file`），确保 ledger 是稳定的、可比较的。

### 如何刷新

```bash
# 刷新全部 ledger
agentplane projection ledger refresh --target prod0-main --write

# 刷新单个应用的 ledger
agentplane app object refresh-ledger --target prod0-main --write
```

---

## 📝 第三层：App Summary（摘要）

### 是什么？

面向人类的**非敏感摘要**，回答："当前正式口径是什么？哪些对象已验证？哪些待人工跟进？"

### 存储位置

**主机级摘要**：
```
inventory/servers/prod0-main/README.md
```

**应用级摘要**（在应用仓库中）：
```
docs/summaries/prod0-main.md
```

### README.md 中的自动生成区块

```markdown
## 1Panel 对象台帐投影
- 生成时间：`2026-04-23T00:49:57.933149+00:00`
- 刷新命令：`uv run python -m agentplane.cli projection ledger refresh --target prod0-main --write`

### 对象计数
- `websites`: 2
- `containers`: 5
- `apps`: 1
- `app_resources`: 1

### 最近 CLI 动作
- `cronjob`: `search` / `queried` / `2026-04-23T00:21:31.938681+00:00`
- `panel`: `verify` / `verified` / `2026-04-23T00:48:56.864599+00:00`
```

### 如何刷新

```bash
# 刷新 ledger 时自动更新 README.md 投影区块
agentplane projection ledger refresh --target prod0-main --write

# 刷新应用级摘要
agentplane app delivery doc-sync --target prod0-main --app sub2api --write
```

---

## 🔄 投影生成流程

### 标准执行闭环

```
Plan（计划）→ Apply（执行）→ Verify（验证）
    ↓
Ledger（写证据）→ Inventory（刷新台账）→ Doc-Sync（同步文档）
```

### Ledger Refresh 内部流程

```
1. 从 inventory.json 提取各类型行
    ↓
2. 从 tmp/operation-ledger/*.jsonl 读取操作记录
    ↓
3. 用 extract_ledger_fields() 过滤 observation-only 字段
    ↓
4. 用 _annotate_rows() 为每行附加 last_cli_operation
    ↓
5. 写 ledgers/<name>.json 和 ledgers/<name>.md
    ↓
6. 回写 inventory.json 的 object_ledgers 区块
    ↓
7. 更新 README.md 的投影区块
```

### 投影依赖关系

```
inventory.json (真源)
    │
    ├──→ ledgers/*.json (从 inventory 行提取 + 操作记录注解)
    │         │
    │         └──→ ledgers/*.md (JSON 的 Markdown 摘要)
    │
    ├──→ inventory.json.object_ledgers (回写 ledger 路径指针 + 计数)
    │
    ├──→ README.md 投影区块 (回写人类可读摘要)
    │
    ├──→ app-resources.json → app_resources ledger
    │
    └──→ app catalog.json → apps ledger
```

---

## 🔍 投影如何支撑对账与审计

### 对账机制

| 对账类型 | 比较对象 | 命令 |
|----------|----------|------|
| **Inventory vs Live State** | Git 声明 vs 实际运行 | `infra audit` |
| **Ledger vs Inventory** | 证据指针 vs 台账条目 | `app object verify` |
| **Runtime Env Drift** | 渲染后 env vs 实际 env 文件 | `projection runtime-env verify` |
| **Operation Receipt** | 操作记录 vs 对象状态 | ledger 中的 `last_cli_operation` |

### 审计支撑

- **操作日志**：`tmp/operation-ledger/*.jsonl` 记录每次 CLI 操作
- **验证结果**：`verification-<profile>.json` 记录验证套件完整结果
- **资源归属**：`app-resources.json` 中的 `ledger_status` 记录隔离级别声明
- **优先级规则**：live state > inventory > ledger > runbook

### 自动化对账

prod0-main 配置了 4 个定时任务，每日自动执行：
1. inventory refresh
2. host audit
3. network audit
4. projection ledger refresh

---

## 🚀 目前支持的能力

### 投影相关命令

| 命令 | 作用 |
|------|------|
| `agentplane infra inventory <target>` | 更新主机 inventory |
| `agentplane infra audit <target>` | 主机治理审计 |
| `agentplane projection ledger refresh --target <t> --write` | 刷新全部 ledger |
| `agentplane projection runtime-env verify --target <t> --app <a>` | 检测 env 漂移 |
| `agentplane projection verification run --target <t> --profile <p>` | 运行验证套件 |
| `agentplane app object verify --target <t> --app <a>` | 核验 app 对象一致性 |
| `agentplane app object refresh-ledger --target <t> --write` | 刷新 apps ledger |
| `agentplane app delivery inventory-refresh --target <t> --app <a> --write` | 应用级 inventory 回写 |
| `agentplane app delivery doc-sync --target <t> --app <a> --write` | 文档同步 |

### 投影生命周期

应用接入时（Onboarding）：
```
inventory projection → runtime environment sync → ledger refresh → doc sync
```

应用退出时（Offboarding）：
```
projection retirement → runtime environment cleanup → ledger retirement → doc sync
```

---

## 🔮 后续可扩展的方向

### 第四层投影：Operation Receipt（操作凭证）

**是什么**：每次正式任务的结构化摘要，回答"这次操作做了什么？结果如何？"

**可能的结构**：
```json
{
  "op_id": "deploy-sub2api-20260430-001",
  "task_entry": "app delivery deploy",
  "target": "prod0-main",
  "app": "sub2api",
  "started_at": "2026-04-30T10:00:00Z",
  "completed_at": "2026-04-30T10:05:00Z",
  "result": "success",
  "steps": [
    { "action": "validate-contract", "result": "ok" },
    { "action": "build-artifact", "result": "ok" },
    { "action": "deploy", "result": "ok" },
    { "action": "verify", "result": "ok" }
  ],
  "evidence_refs": [
    "inventory/servers/prod0-main/ledgers/apps.json",
    "tmp/operation-ledger/deploy-sub2api-20260430.jsonl"
  ]
}
```

**价值**：让每次操作都有可追溯的"收据"，支持审计、复盘和趋势分析。

### 第五层投影：Exception Review（异常复盘）

**是什么**：失败、紧急绕过、回滚、审批拒绝后的学习材料。

**可能的结构**：
```json
{
  "review_id": "exception-deploy-sub2api-20260430",
  "trigger": "deploy_failed",
  "task_entry": "app delivery deploy",
  "target": "prod0-main",
  "app": "sub2api",
  "root_cause": "容器镜像拉取失败",
  "impact": "服务中断 5 分钟",
  "resolution": "手动回滚到上一版本",
  "lessons": [
    "镜像仓库需要配置重试机制",
    "部署前应检查镜像是否存在"
  ],
  "follow_up": [
    { "action": "添加镜像存在性检查", "owner": "maintainer", "deadline": "2026-05-07" }
  ]
}
```

**价值**：把失败转化为学习材料，避免重复犯错。

### 第六层投影：Trend Report（趋势报告）

**是什么**：帮助人类判断哪些能力应该改进的统计报告。

**可能的内容**：
- 哪些 Skill 最常被使用？
- 哪些命令最常失败？
- 哪些对象的 ledger 最常过期？
- 哪些操作最常需要人工介入？

**价值**：用数据驱动改进，而不是凭感觉。

### 其他扩展方向

| 方向 | 说明 |
|------|------|
| **多 target 聚合视图** | 跨多个服务器的统一视图 |
| **时间序列投影** | 记录状态变化历史，支持回溯 |
| **告警投影** | 当 ledger 过期或验证失败时自动告警 |
| **合规投影** | 检查是否符合安全基线 |
| **成本投影** | 跟踪资源使用和成本 |

---

## 📖 关键概念速查

| 概念 | 含义 |
|------|------|
| **真源 (Source of Truth)** | 某一类事实的正式来源，如 Git 配置、inventory、ledger |
| **投影 (Projection)** | 从真源派生的只读视图，不存储原始数据 |
| **Inventory** | 目标环境的正式非敏感台账 |
| **Ledger** | 围绕某类对象生成的机器派生记录 |
| **App Summary** | 面向人类的非敏感摘要 |
| **Live State** | 通过现场命令/API 获取的当前真实状态 |
| **Task Entry** | 面向 Agent 的正式任务入口 |
| **Skill** | AI Agent 的意图入口，负责路由到 CLI |

---

## 🔗 关联文档

- [入门指南](getting-started.md) — 快速了解 AgentPlane
- [控制面核心合同](../architecture/control-plane.md) — 投影模型的权威定义（面向 AI）
- [术语表](../reference/glossary.md) — 核心术语统一定义
- [项目定位](../reference/project-positioning.md) — AgentPlane 的边界和适用场景
