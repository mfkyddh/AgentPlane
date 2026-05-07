---
status: active
owner: AgentPlane maintainers
last_verified: 2026-05-07
audience: both
---

# AgentPlane 架构

> 本文是 AgentPlane 架构的唯一正文真源。按照"从简单到复杂"的原则组织，让读者能够顺畅地理解整个架构。

---

## 快速理解

### AgentPlane 是什么

**AgentPlane** 是给 AI Agent 用的运维控制面，让 AI 帮你安全地管理应用。

### 怎么工作

```
人类说目标 → AI 匹配 Skill → CLI 执行操作 → 验证结果 → 写回投影
```

1. 你说目标（"部署这个应用"）
2. AI 找到对应的 Skill
3. Skill 调用 CLI 执行操作
4. CLI 验证结果并记录证据

### 核心概念一览

| 概念 | 是什么 | 为什么需要 |
|------|--------|-----------|
| **投影** | 从真源派生出的只读视图 | 把分散的信息聚合在一起，方便查看 |
| **真源** | 某一类事实的正式来源 | 确保数据的一致性和可靠性 |
| **CLI** | 命令行界面 | 统一入口，Agent 和人类都可以使用 |
| **Skill** | AI Agent 的能力入口 | 让 AI 理解人类意图，路由到 CLI |
| **域** | AgentPlane 的 5 个业务能力域（infra、service、app、ingress、project） | 每个域对应项目模型的一层，职责分离 |

---

## 核心概念

在深入了解架构之前，先理解几个核心概念。

### 什么是投影？

**投影**（Projection）是从**真源**派生出的**只读视图**。

就像数据库的视图一样，投影不存储原始数据，而是从真源计算得出。

**为什么需要投影？**
- 真源可能分散在多个地方（Git 配置、现场状态、Ledger 等）
- 投影把这些信息聚合在一起，方便查看
- 投影是只读的，不会修改真源

**示例**：
- 你想知道"这个服务器上有哪些服务" → 查看 Host Inventory
- 你想知道"这个服务最近一次验证结果是什么" → 查看 Object Ledgers
- 你想知道"这个应用当前状态是什么" → 查看 App Summary

### 什么是真源？

**真源**（Source of Truth）是某一类事实的正式来源。

**AgentPlane 的真源**：
- **Git 配置**：我们期望系统应该是什么样
- **Live State**：系统实际是什么样
- **Inventory**：我们记录的系统状态
- **Ledger**：我们验证的结果

**为什么需要真源？**
- 确保数据的一致性和可靠性
- 避免多个地方存储相同信息，导致不一致
- 提供可追溯性，知道信息从哪里来

**真源优先级**：
```
Live State（现场状态）> Inventory（台账）> Ledger（证据）> Runbook（文档）
```

Live State 优先级最高，因为它是"实际发生了什么"，而不是"我们希望发生什么"。

### 什么是 CLI？

**CLI**（Command-Line Interface）是命令行界面。

**AgentPlane 的 CLI**：
- 形态：`agentplane <domain> <surface> <verb> [flags]`
- 所有正式操作必须从 CLI 进入
- CLI 是 Agent 和人类的统一入口

**为什么必须从 CLI 进入？**
- 统一入口：Agent 和人类都使用同一套命令
- 可审计：所有操作都有记录
- 可验证：所有操作都有验证
- 可回滚：所有操作都有证据

**示例**：
```bash
# 搜索服务
agentplane service search --target prod0-main

# 验证应用
agentplane app delivery verify --target prod0-main --app myapp

# 部署应用
agentplane app delivery deploy --target prod0-main --app myapp --dry-run
```

### 什么是 Skill？

**Skill** 是 AI Agent 理解人类意图后选择的能力入口。

**Skill 的职责**：
- 路由到正式 `agentplane ...` CLI
- 提示前置检查
- 说明验证与回写

**Skill 不做什么**：
- 不执行第二套逻辑
- 不直接拼 SSH、Docker 或 provider API

**为什么需要 Skill？**
- 让 AI 理解人类意图，而不是直接执行命令
- 提供统一的入口，避免 AI 绕过 CLI
- 支持前置检查，确保操作安全

**示例**：
- 你说："帮我部署这个应用"
- AI 找到 Skill：`app-delivery-ops`
- Skill 调用 CLI：`agentplane app delivery deploy --target prod0-main --app myapp --dry-run`

---

## 域

**域**（Domain）是 AgentPlane 的职责划分。每个域对应项目模型中的一个管理层次——项目模型是"管什么"，域是"怎么管"。

### 5 个业务能力域

| 域 | 管什么 | 管理阶段 | 对应项目模型 |
|---|---|---|---|
| `infra` | Target 配置（主机、网络、Secrets） | 配置层：Target 应该是什么样 | **Target** |
| `service` | 运行时管理（所有 Docker 容器的健康、重启、日志） | 运行层：实际跑着什么 | Target 上的**运行时** |
| `app` | 应用交付生命周期（catalog、构建、部署、回滚） | 交付层：怎么把 App 送到 Target | **App** |
| `ingress` | 公网入口（域名、SSL、路由） | 流量层：外部怎么访问 | App 的**对外访问** |
| `project` | 项目治理（分组、聚合状态、项目级配置） | 组织层：怎么分组管理 | **Project** |

### 域与项目模型的对应关系

项目模型是"管什么"，域是"怎么管"。每一层项目模型都有对应的管理能力：

```
Project ─────→ project 域（项目治理、聚合状态）
  └── App ───→ app 域（交付生命周期）
        └── Target ─→ infra 域（配置）+ service 域（运行时）
              └── 公网入口 → ingress 域
```

### 基础设施也是应用

PostgreSQL、Redis、MinIO 等基础设施服务，作为 App 管理在一个专门的基础设施项目中，与其他业务项目共享。没有特例——所有应用用同一套流程管理。

```
Project: infrastructure          Project: mall-system
├── App: postgres                ├── App: order-service
├── App: redis                   ├── App: payment-gateway
├── App: minio                   └── App: user-service
└── App: nginx
```

### 域之间的协作

```
app deploy 创建容器 → service 接管运行时管理
infra 配置 Target → service 在 Target 上运行容器
project 聚合状态 ← 从 app 和 service 收集
```

> `projection`（投影和验证）是所有域共用的横切机制，见"三层投影模型"章节。
> `onepanel`（1Panel provider）是 provider 层的实现细节，见 [技术栈](tech-stack.md)。

### 使用场景

| 你想做什么 | 使用哪个域 | 示例命令 |
|-----------|-----------|---------|
| 配置服务器 | `infra` | `agentplane infra ...` |
| 查看运行中的容器 | `service` | `agentplane service search --target prod0-main` |
| 部署或回滚应用 | `app` | `agentplane app deploy --target prod0-main --app myapp` |
| 管理公网入口 | `ingress` | `agentplane ingress ...` |
| 查看项目整体状态 | `project` | `agentplane project status --project mall-system` |

---

## 三层投影模型

投影是 AgentPlane 的核心数据模型，分为三层。

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

### 第一层：Host Inventory（台账）

**是什么**：记录某个 Target 有哪些受管对象。

**包含内容**：
- 服务器列表
- 服务列表
- 应用列表
- 入口列表

**如何生成**：从 Live State 和 Git 配置计算得出。

**何时更新**：每次执行 `agentplane infra inventory` 时更新。

**示例**：
```bash
# 查看某个 Target 的 inventory
agentplane infra inventory prod0-main --repo-root .
```

### 第二层：Object Ledgers（证据）

**是什么**：围绕对象或操作生成的机器派生验证记录。

**包含内容**：
- 验证结果
- 操作记录
- 错误信息

**如何生成**：从 Live State 验证得出。

**何时更新**：每次执行 `agentplane ... verify` 时更新。

**示例**：
```bash
# 验证某个服务
agentplane service verify --target prod0-main --name myapp
```

### 第三层：App Summary（摘要）

**是什么**：面向人类的当前状况摘要。

**包含内容**：
- 应用状态
- 服务状态
- 最近操作

**如何生成**：从 Host Inventory 和 Object Ledgers 计算得出。

**何时更新**：每次执行 `agentplane repo status` 时更新。

**示例**：
```bash
# 查看仓库状态
agentplane repo status --repo-root .
```

### 标准执行闭环

所有操作遵循标准执行闭环：

```
Plan（计划）→ Apply（执行）→ Verify（验证）
    ↓
Ledger（写证据）→ Inventory（刷新台账）→ Doc-Sync（同步文档）
```

**为什么需要执行闭环？**
- 安全：执行前有计划
- 可靠：执行后有验证
- 可追溯：所有操作有记录
- 可回滚：记录支持回滚

**示例**：
```bash
# 1. Plan（计划）
agentplane service plan --target prod0-main --name myapp --operation restart

# 2. Apply（执行）
agentplane service apply --target prod0-main --name myapp --execute

# 3. Verify（验证）
agentplane service verify --target prod0-main --name myapp

# 4. Ledger（写证据）— 自动完成
# 5. Inventory（刷新台账）— 自动完成
# 6. Doc-Sync（同步文档）— 自动完成
```

---

## CLI 接口规范

### 命令形态

AgentPlane 的命令遵循统一形态：

```bash
agentplane <domain> <surface> <verb> [flags]
```

**组成部分**：
- `<domain>`：域，如 `infra`、`service`、`app`、`ingress`、`project`
- `<surface>`：对象面或工作流面。**对象面**操作单个对象（如 `service`、`app object`），**工作流面**执行跨对象的流程（如 `app delivery`）
- `<verb>`：动作，如 `search`、`get`、`plan`、`apply`、`verify`
- `[flags]`：可选参数

**示例**：
```bash
# 对象面：搜索服务
agentplane service search --target prod0-main

# 工作流面：部署应用
agentplane app delivery deploy --target prod0-main --app myapp --dry-run
```

### Verbs

**Verbs**（动词）是命令中的动作部分，即"你想做什么"。在 `agentplane <domain> <surface> <verb>` 中，verb 决定操作类型。

AgentPlane 的 verbs 分为两类：

**对象面**：`search`、`get`、`plan`、`apply`、`verify`、`refresh-ledger`

**工作流面**：`suite`、`run`、`fixture`、`onboard`、`migrate`、`doctor`

**什么时候用对象面**：边界稳定、选择器稳定、动作集合清晰、结果可验证

**什么时候用工作流面**：跨主机、多阶段切换、依赖现场判断、失败补偿复杂

### 公共 Flags

| Flag | 说明 |
|------|------|
| `--target` 或 `--env` | 指定目标环境 |
| `--repo-root` | 指定仓库根目录 |
| `--json` | 输出 JSON 格式 |
| `--write` | 写入文件 |
| `--dry-run` | 预览模式，不执行 |
| `--execute` | 执行模式，与 `--dry-run` 互斥 |

### 输出规范

- 机器可解析结果写 `stdout`
- 诊断、提示、警告写 `stderr`
- 默认文本模式面向人类；`--json` 模式面向 Agent

### 错误 Envelope

**Envelope**（信封）是软件工程中的一种标准化包装格式。**错误 Envelope** 是 CLI 返回错误时的统一 JSON 结构——无论什么错误，格式都一样，方便 Agent 解析。

```json
{
  "ok": false,
  "error": {
    "code": "onepanel.object_not_found",
    "hint": "use search first",
    "message": "website token not found"
  },
  "payload": null,
  "evidence": [],
  "artifacts": []
}
```

**为什么需要错误 Envelope？**
- 统一错误格式，方便解析
- 提供错误码，方便定位问题
- 提供提示，方便修复问题

### 正式入口优先级

```
agentplane.cli > internal implementation asset > runbook > ad-hoc shell
```

**为什么有这个优先级？**
- 统一入口：优先使用 CLI
- 可审计：CLI 提供完整的审计记录
- 可验证：CLI 提供完整的验证机制

---

## 任务入口模型

### 什么是任务入口？

**任务入口**（Task Entry）是面向 Agent 的正式任务入口。

### 任务入口的设计原则

1. **名称表达任务结果**，而不是底层实现
2. **输入优先使用稳定业务引用**
3. **内部可以解析并操作多个对象**
4. **输出必须是 Agent 可继续消费的稳定结果**

**为什么需要任务入口？**
- 让 AI 理解"要做什么"，而不是"怎么做"
- 提供稳定的接口，避免底层实现变化影响上层
- 支持多对象操作，简化复杂任务

**示例**：
```bash
# 任务入口：部署应用
agentplane app delivery deploy --target prod0-main --app myapp

# 内部可能操作多个对象：
# 1. 验证 contract.yaml
# 2. 构建镜像
# 3. 更新 compose 文件
# 4. 重启服务
# 5. 验证健康状态
```

---

## 跨平台执行模型

### 执行路径

```
Windows 宿主
  ├── Windows 原生命令 → pwsh
  ├── 需要 Linux 环境 → wsl.exe -e <程序> <参数>
  │   └── 需要管道/重定向 → wsl.exe bash -lc "cmd1 | cmd2 > out"
  └── 远程 Linux → agentplane infra remote bash
```

**为什么需要跨平台执行？**
- 开发环境可能是 Windows
- 生产环境通常是 Linux
- 需要统一的执行方式

### 核心约束

- Windows 和 WSL **共用同一份源码 checkout**
- 每个物理 checkout **只保留一个 `.venv`**
- 不设置平台专属的 `UV_PROJECT_ENVIRONMENT`
- 跨平台路径处理优先使用 runtime/path policy

**为什么有这些约束？**
- 避免环境不一致导致的问题
- 简化开发和部署流程
- 提高可维护性

### Runtime Backend 注册

```python
@register_backend("type")
class SomeBackend:
    ...
```

Backend 自注册模式：Windows → WSL → SSH → Linux native，由 resolver 自动选择。

**为什么需要 Runtime Backend？**
- 支持多种执行环境
- 自动选择最合适的执行方式
- 易于扩展新的执行环境

---

## 应用层协作

### 职责边界

**AgentPlane 负责**：
- 管理 Target 配置（主机、网络、Secrets）
- 管理所有应用的交付和运行时（包括基础设施应用和业务应用）
- 管理正式部署、发布切换、回滚、inventory

**应用层项目负责**：
- 业务代码、测试、Dockerfile、镜像构建脚本
- `deploy/agentplane/contract.yaml`（非敏感交付合同）
- 不保存生产 secrets、SSH 密钥、正式 inventory

**基础设施也是应用**：PostgreSQL、Redis、MinIO 等基础设施服务，通过专门的基础设施项目管理，与业务应用使用相同的交付和运行时流程。

**为什么这样划分？**
- 统一管理：所有应用（基础设施和业务）用同一套流程
- 安全性：生产 secrets 不进入应用仓库
- 可维护性：基础设施服务可以像业务应用一样版本管理、回滚

### 应用交付合同

每个应用仓库必须提供 `deploy/agentplane/contract.yaml`：

```yaml
schema_version: 2
app_id: sub2api
artifact:
  build_command: bash deploy/build-runtime-artifacts.sh
  output_path: dist/oplinux
packaging:
  image_name: sub2api-prod
  image_tag_rule: <upstream>-zzz.<yyyymmdd>.v<n>.g<gitsha>
runtime:
  kind: compose
  container_name: sub2api-prod
  container_port: 8080
  host_binding: 127.0.0.1:18080
  healthcheck:
    path: /health
    expected_status: 200
```

**为什么需要应用交付合同？**
- 明确应用的交付边界
- 支持自动化部署和验证
- 避免配置不一致导致的问题

### 容器命名

- 正式应用：`<app>-prod`
- WSL 开发：`<app>-dev`
- 基础设施：显式稳定名（如 `postgres18-prod`）

**为什么这样命名？**
- 易于识别：一看就知道是什么环境
- 避免冲突：不同环境使用不同名称
- 易于管理：可以按名称批量操作

---

## WebUI 架构

### WebUI 的定位

WebUI 是控制面的可视化视图，不是新的控制面入口。

```
WebUI (FastAPI + uvicorn) → domain handlers → runtime → providers
     ↑
CLI (argparse) → domain handlers → runtime → providers
```

两者共享同一个 domain 层，WebUI 是一个薄展示层。

**为什么 WebUI 不是新的控制面入口？**
- 统一入口：所有操作必须从 CLI 进入
- 可审计：CLI 提供完整的审计记录
- 可验证：CLI 提供完整的验证机制

### 技术实现

- 启动：`agentplane web --host 127.0.0.1 --port 8080`
- 前端：Vue 3 CDN 模式，无需构建工具
- 后端：FastAPI + uvicorn
- Agent 聊天：通过 Claude API，仅支持只读命令

---

## 关联文档

- [愿景](vision.md) — 项目定位、目标用户、项目模型
- [原则](principles.md) — 道法术三层原则体系
- [路线图](roadmap.md) — Alpha → Beta → GA 三阶段推进
- [入门指南](getting-started.md) — 快速了解
- [命令参考](command-reference.md) — 所有 CLI 命令
- [技术栈](tech-stack.md) — 技术选型与跨平台规范
- [WebUI](webui.md) — WebUI 架构和使用
- [Maintainer 指南](maintainer-guide.md) — 治理资产约束和协作规则
