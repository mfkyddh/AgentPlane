---
status: active
owner: AgentPlane maintainers
last_verified: 2026-04-30
superseded_by: null
audience: human
---

# 🧭 AgentPlane 入门指南

结论：AgentPlane 是一套让 AI 安全接管基础设施的"遥控器"系统。你下指令，AI 先匹配 Skill，再通过 `agentplane ...` 执行，全程有计划、有验证、有记录。

---

## 😰 你是否遇到过这些情况？

让 AI 帮你运维服务器，结果：

```bash
# AI 直接执行原始命令
ssh prod "docker restart myapp"
```

- **SSH 连不上？** 失败后才知
- **容器起不来？** 错误淹没在输出中
- **服务真的好了吗？** 没有验证
- **谁执行的？什么时候？** 查不到
- **想回滚？** 没有任何记录

这就是让一个没有安全护栏的机器人直接操作生产线。

---

## ✅ AgentPlane 怎么解决？

所有操作通过 `agentplane ...` 标准化入口执行，每个入口自动完成：

```
检查依赖 → 执行操作 → 验证结果 → 留下记录
```

同样的需求，不同的体验：

```bash
$ agentplane service apply --target prod --name myapp --execute

[检查] 主机在线 ✓
[执行] 重启容器 myapp ✓
[验证] HTTP 探针 200 OK ✓
[记录] 操作已保存，可随时回查
```

**核心理念：配置中心 vs 现场状态**

- **配置中心**：Git 里的文件定义"我们希望系统是什么样"——这是权威定义
- **现场状态**：服务器上实际运行的容器和服务——这是验证基准
- AgentPlane 的工作就是**持续对比两者**，发现不一致时及时报告

> 💡 为什么不用现场状态当权威？因为现场状态今天对、明天可能就被手动改乱了。Git 里的配置可以回滚到任意历史版本。

---

## 🤖 AI 是怎么工作的？

当你对 AI 说：

> "把 sub2api 部署到 prod0-main，用最新镜像，先预览变更，确认后再执行。"

AI 会执行以下流程：

```
1. 理解意图 → 2. 匹配 Skill → 3. 制定计划 → 4. 向你确认
5. 执行操作 → 6. 验证结果 → 7. 留下记录 → 8. 向你汇报
```

### 第 1 步：理解意图

AI 会把你的自然语言翻译成结构化意图：

| 要素 | 你的输入 | AI 的理解 |
|------|---------|----------|
| 目标 | 部署 sub2api | 应用交付操作 |
| 环境 | prod0-main | 目标主机 |
| 版本 | 最新镜像 | 使用最新构建的镜像 |
| 约束 | 先预览再执行 | 必须走 Plan → Apply 两步 |

### 第 2 步：匹配 Skill

AI 会从 `.agents/skills` 中选择能力入口。这个例子会匹配 `app-delivery-ops`，因为它负责应用合同校验、构建、部署、验证、状态刷新和摘要回写。

Skill 会提醒 AI：

- 先校验合同，再构建和部署
- 部署先 `--dry-run`，确认后才 `--execute`
- 执行后必须验证并回写非敏感摘要
- 不要绕到原始 SSH、Docker 或 provider API

### 第 3 步：制定计划

AI 生成具体的执行计划：

```bash
agentplane app delivery validate-contract --target prod0-main --app sub2api
agentplane app delivery build-artifact --target prod0-main --app sub2api --image-tag latest
agentplane app delivery deploy --target prod0-main --app sub2api --dry-run
```

### 第 4 步：向你确认

AI 会停下来问你：

> "计划如下：先校验交付配置，再构建镜像，最后预览部署。预计变更：更新容器 sub2api-prod，重启 1 个服务。是否继续？"

**这是人类的第一个介入点**。如果你不同意，AI 会重新调整计划。

### 第 5 步：执行操作

你确认后，AI 才会加上 `--execute` 真正执行：

```bash
agentplane app delivery deploy --target prod0-main --app sub2api --execute
```

### 第 6 步：验证结果

执行后，AI 必须验证：

```bash
agentplane app delivery verify --target prod0-main --app sub2api --execute
```

验证内容包括：容器是否运行、健康检查是否通过、公网入口是否可访问。

### 第 7 步：留下记录

AI 会自动：
- 把操作记录写入机器证据目录（`tmp/operation-logs/`）
- 刷新状态记录目录（`inventory/`）
- 更新相关文档摘要

### 第 8 步：向你汇报

AI 会给你一份人类可读的摘要：

> "已完成 sub2api 到 prod0-main 的部署。验证结果：容器运行正常，HTTP 探针 200 OK，公网入口 https://token.example.net:8443 可访问。操作记录已保存。"

---

## 🎯 核心概念速查

| 概念 | 含义 | 类比 |
|------|------|------|
| **配置中心** | Git 中的权威状态定义，回答"我们期望系统应该是什么样" | 仓库的"货物清单" |
| **Skill** | AI Agent 的意图入口，负责把自然语言路由到正式 CLI | 仓库的"调度员" |
| **标准化入口** | AI 不直接操作底层资源，而是通过 `agentplane ...` 执行任务 | 仓库的"操作手册" |
| **执行闭环** | Plan → Apply → Verify → 记录 → 刷新台账 → 同步文档 | 仓库的"标准流程" |
| **三层投影** | Inventory（声明）→ Ledger（证据）→ Summary（摘要） | 仓库的"清单→盘点→报告" |

**三层投影速览**：

| 层级 | 本质 | 来源 | 回答的问题 |
|------|------|------|-----------|
| **Inventory（台账）** | 声明 | Git 配置 | "我们声明了要管理什么？" |
| **Ledger（证据）** | 验证 | 现场验证 | "系统实际有什么？" |
| **Summary（摘要）** | 结论 | 派生 | "当前状况如何？" |

**为什么需要三层？** 因为"声明"和"实际"经常不一致。Inventory 说"应该有 redis"，但 Ledger 说"redis 没在运行"——这就是问题！

**Skill 路由示例**：

| 你的说法 | AI 选择的 Skill | 正式入口 |
|----------|-----------------|----------|
| 部署一个应用 | `app-delivery-ops` | `agentplane app delivery ...` |
| 检查服务状态 | `agentplane-service-ops` | `agentplane service ...` |
| 纳管新主机 | `host-onboarding-ops` | `agentplane bootstrap ...` / `agentplane infra ...` |
| 发布网站入口 | `agentplane-ingress-ops` | `agentplane ingress ...` |

---

## 👥 人类与 AI 的分工

| 责任 | 人类 | AI |
|------|:---:|:---:|
| 定目标 | ✅ 描述你要做什么 | ❌ |
| 定约束 | ✅ 说清边界和风险接受度 | ❌ |
| 制定计划 | ❌ | ✅ 生成可执行计划 |
| 选择 Skill | ❌ | ✅ 匹配能力入口和边界 |
| 确认计划 | ✅ 审核并批准 | ❌ |
| 执行操作 | ❌ | ✅ 通过 `agentplane ...` 执行 |
| 验证结果 | ❌ | ✅ 运行验证命令 |
| 验收 | ✅ 看摘要和证据 | ❌ |
| 异常处理 | ✅ 关键决策 | ✅ 初步排查和回滚建议 |

**人类什么时候必须介入？**

| 场景 | 为什么需要人工 |
|------|--------------|
| 高风险正式切换 | 可能影响生产服务可用性 |
| 证书、域名、入口变更 | 涉及公网可达性，错误代价高 |
| 数据迁移或回滚 | 可能导致数据丢失 |
| 计划输出与预期明显不一致 | AI 可能对现场状态理解有误 |
| 验证结果与预期冲突 | 需要人工判断是预期错了还是现场错了 |

> ⚠️ **你的权力**：任何时候你都可以说"停"，AI 会立即停止执行。

---

## 🧭 怎么跟 AI 协作？

AgentPlane 的协作模式是：**你用自然语言表达意图，AI 自主推进全部实施工作。**

你不需要记命令、不需要写代码、不需要管 git——只需要告诉 AI 你想做什么。

### 主线与分支

项目有一条**主线**（当前阶段必须完成的三件事）。你提的每个需求，AI 会自动判断归属：

| 归属 | 说明 | 例子 |
|------|------|------|
| **主线** | 直接服务当前阶段目标 | "给 infra-ops 补测试" |
| **分支** | 间接相关，做完回归主线 | "修一下这个文档的错别字" |
| **backlog** | 有价值但当前不需要 | "以后支持插件系统" |

**你不需要记住主线是什么**。AI 每次会话开始会告诉你当前位置，做完事情会更新进度。

### 会话流程

每次跟 AI 协作的标准流程：

```
1. AI 报告当前进度（"上次我们在 XX"）
2. 你说需求（"帮我做 YY"）
3. AI 判断归属，制定计划
4. 你确认（或调整）
5. AI 自主执行
6. AI 自动验证
7. AI 给你交付报告
8. AI 更新进度记录
```

### 你可以随时做的事

| 你说 | AI 会做 |
|------|--------|
| "继续推进主线" | 从上次停下的地方继续 |
| "帮我部署这个应用" | 匹配 Skill，执行部署 |
| "这个 bug 怎么回事" | 调查、修复、验证 |
| "我有个新想法" | 评估归属，安排执行或记录 |
| "先不管这个，做另一个" | 切换任务，不丢失进度 |
| "停" | 立即停止 |

### 进度追踪

AI 使用 `docs/project/backlog.md` 追踪主线进度。你可以随时查看这个文件，了解：
- 主线三个条件的完成情况
- 当前进行中的分支任务
- 暂不执行的 backlog 条目

详细协作规则见 [人机协作协议](../reference/human-ai-collaboration.md)。

---

## 🚀 下一步：动手试试

### 体检你的环境

```bash
# 1. 检查本地环境
agentplane bootstrap inspect-local --repo-root .

# 2. 运行诊断
agentplane bootstrap doctor --repo-root .

# 3. 初始化 secrets
agentplane bootstrap init-secrets --repo-root .

# 4. 验证 secrets
agentplane bootstrap verify-secrets --repo-root .
```

### 查看项目状态

```bash
# 生成状态报告
agentplane repo status --repo-root . --html tmp/agentplane-status.html

# 运行健康检查
agentplane repo health-check --repo-root .
```

### 更多资源

- **想上手部署？** → [应用交付流程](../runbooks/app-project-delivery-workflow.md)
- **想了解 AI 执行规范？** → [AI 执行闭环](../runbooks/control-plane-agent-execution-flow.md)
- **想深入架构设计？** → [控制面核心合同](../architecture/control-plane.md)
- **想知道当前状态？** → [状态与验证](../runbooks/current-state-and-validation.md)
- **想看术语定义？** → [术语表](../reference/glossary.md)

---

## 🔗 关联文档

- [AGENTS.md](../../AGENTS.md) — AI 的完整工作规范
- [Skill 盘点](../history/skill-surface-audit.md) — 历史 Skill 能力面快照
- [愿景](../strategy/vision.md) — AgentPlane 的边界和适用场景
