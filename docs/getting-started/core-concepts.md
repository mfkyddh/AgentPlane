---
status: active
owner: AgentPlane maintainers
last_verified: 2026-04-25
superseded_by: null
audience: human
---

# 🧠 AgentPlane 核心概念

结论：AgentPlane 的核心是三个机制——标准化入口（AI 不直接操作底层，走统一命令）、配置中心模型（Git 管期望状态，现场只做验证）、执行闭环（Plan → Apply → Verify → 记录 → 刷新台账 → 同步文档）。

---

## 1️⃣ 配置中心与三层状态

在系统管理中，"配置中心"是指被所有组件共同承认的**权威状态定义**。

AgentPlane 的核心工作是**持续对比以下三层状态**：

| 状态层级 | 来源 | 回答的问题 | 示例 |
|---------|------|-----------|------|
| **期望状态** | Git 中的配置文件 | "我们期望系统应该是什么样？" | Compose 文件定义了 3 个容器 |
| **实际状态** | 现场实时查询 | "系统实际是什么样？" | `docker ps` 只显示 2 个容器在运行 |
| **观测状态** | 结构化台账 | "上次验证时记录的状态是什么？" | 台账中记录了 2 个容器 |

**对比示例**：Git 中的 Compose 文件定义了 3 个容器，但现场只运行了 2 个——这就是期望状态与实际状态的不一致，需要处理。

> 💡 **为什么不用现场状态作为配置中心？** 因为现场状态是易变的、不可追溯的。今天容器在运行，明天可能被手动停掉了。Git 管理的配置可以回滚到任意历史版本，而现场状态不能。

---

## 2️⃣ 标准化入口

标准化入口回答的问题是：**"AI 应该怎么操作基础设施？"**

**传统方式的问题**：

```bash
# ❌ 危险：AI 直接执行原始命令
ssh user@prod-server "docker restart myapp"
```

- **没有前置检查**：SSH 连不上？容器不存在？你只能在失败之后才知道
- **没有错误处理**：命令输出什么错误？怎么恢复？全靠人工解读
- **没有审计记录**：谁执行了这个操作？什么时候？查不到
- **没有状态验证**：容器重启了，但服务真的正常了吗？不知道

**AgentPlane 的方式**：

```bash
# ✅ 安全：通过标准化入口操作
$ agentplane service verify --target prod0-main --name myapp

[检查] 目标主机 prod0-main 在线 ✓
[检查] 容器 myapp 存在，状态: running ✓
[验证] HTTP 健康检查: 200 OK ✓
[审计] 操作已保存，可随时回查
```

每个标准化入口都封装了：

1. **前置检查** — 自动验证主机在线、容器存在等依赖条件
2. **后端路由** — 自动选择 WSL / SSH / Docker 执行后端
3. **错误处理** — 结构化错误 + 恢复建议
4. **审计记录** — 自动写入操作记录，完整保留操作上下文

**对象分层**：

AgentPlane 把基础设施抽象为 4 个对象域：

| 对象域 | 管理内容 | 典型命令 |
|--------|---------|---------|
| `infra` | 主机资产、SSH 连接、网络治理 | `infra inventory`、`infra audit`、`infra remote bash` |
| `service` | 运行中的服务（容器、数据库等） | `service search`、`service verify`、`service apply` |
| `ingress` | 公网入口、域名、证书 | `ingress publish plan`、`ingress verify` |
| `app` | 应用交付（构建、部署、回滚） | `app delivery validate-contract`、`app delivery deploy` |

---

## 3️⃣ 跨平台解析

AgentPlane 支持 Windows、Linux、macOS 三种宿主环境。路径转换层负责**把统一的逻辑路径解析为当前平台可执行的具体操作**。

> 💡 **逻辑路径 vs 物理路径**：Git 仓库中的文件位置是逻辑路径（如 `infra/compose/sub2api/docker-compose.prod0.yml`），它不包含任何平台信息。而物理路径是操作系统实际访问文件时的绝对路径（如 `D:/Projects/...` 或 `/mnt/d/...`）。

**设计原则**：平台差异只留在解析层，上层的命令和文档完全平台无关。这意味着同一套命令在所有平台上都执行。

---

## 4️⃣ 执行闭环

AgentPlane 对任何影响正式状态的操作，都强制遵循 **6 步闭环**：

```
1. Plan（计划）→ 2. Apply（执行）→ 3. Verify（验证）
→ 4. 记录（机器证据）→ 5. 刷新状态台账 → 6. 同步文档摘要
```

| 阶段 | 作用 | 关键规则 |
|------|------|----------|
| **Plan** | 预览将要执行的操作，不改变系统状态 | `--dry-run` 与 `--execute` 互斥 |
| **Apply** | 在计划确认后真正执行变更 | 高风险操作必须通过计划阶段后才能执行 |
| **Verify** | 执行后验证系统是否达到预期状态 | 优先检查实际运行状态，而非文档 |
| **记录** | 把操作过程写入机器可读的证据文件 | 用于故障排查和审计追溯 |
| **刷新台账** | 基于最新现场状态更新结构化状态表 | 确保状态表与现场一致 |
| **同步文档** | 把操作结果回写到人类可读的文档 | 让非技术人员也能了解系统状态 |

---

## 🔑 概念速查

| 概念 | 含义 |
|------|------|
| 配置中心 | 被所有系统承认的权威状态定义，Git 中的配置文件就是配置中心 |
| 标准化入口 | AI 不直接操作底层资源，而是通过高层语义化命令执行任务 |
| 路径转换器 | 把与平台无关的逻辑路径解析为当前平台可访问的物理路径 |
| 操作记录 | 机器生成的操作证据文件，用于故障排查和审计追溯 |
| 状态台账 | 目标环境所有受管对象的摘要快照，用于快速查询和对账 |
| 现场状态 | 通过现场命令或 API 获取的系统真实运行状态 |

> 📌 本文档使用日常说法。如需精确术语定义，请查看 [control-plane.md](../architecture/control-plane.md)。

---

## 🧭 下一步

- **想上手操作？** → [README.md](../../README.md#快速开始)
- **想了解应用交付的详细步骤？** → [app-project-delivery-workflow.md](../runbooks/app-project-delivery-workflow.md)
- **想了解 Agent 的执行规范？** → [control-plane-agent-execution-flow.md](../runbooks/control-plane-agent-execution-flow.md)
- **想了解控制面架构设计？** → [control-plane.md](../architecture/control-plane.md)
- **想知道当前项目状态？** → [current-state-and-validation.md](../runbooks/current-state-and-validation.md)
