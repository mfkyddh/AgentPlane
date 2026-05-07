---
status: active
owner: AgentPlane maintainers
last_verified: 2026-04-30
superseded_by: null
audience: both
layer: project
---

# AgentPlane 主线追踪器

结论：本文是 AgentPlane 唯一的任务真相源。所有工作必须归属于主线条件、分支任务或 backlog 三者之一。AI 每次会话开始时读取本文，结束时更新本文。本文只负责任务推进，不定义产品/项目模型（模型定义见 [术语表](../reference/glossary.md)）。

---

## 🎯 主线：让 AI 能通过 Skill 完成首次运行闭环

当前阶段的唯一目标：**开源用户单 checkout 后，能让 AI 通过 Skill 完成首次运行闭环。** 所有工作都应直接或间接服务于这个目标。

以下三个条件是这个目标的验收口径：

### 条件一：核心 Skill 测试覆盖

| Skill | 状态 | 说明 |
|-------|------|------|
| agentplane-infra-ops | 待评估 | 对应 tests/infra_* |
| agentplane-app-ops | 待评估 | 对应 tests/app_* |
| agentplane-service-ops | 待评估 | 对应 tests/service* |
| agentplane-ingress-ops | 待评估 | 对应 tests/ingress* |
| agentplane-projection-ops | 待评估 | 对应 tests/projection* |
| agentplane-repo-ops | 待评估 | 对应 tests/repo_* |
| app-delivery-ops | 待评估 | 对应 tests/app_delivery* |
| docker-service-setup | 待评估 | workflow skill |
| host-onboarding-ops | 待评估 | workflow skill |
| site-migration-ops | 已完成 | 12 tests |
| tencent-cloud-service-migration | 已完成 | 12 tests |
| nginxui-letsencrypt | 已完成 | 12 tests |
| toolchain-setup | 待评估 | workflow skill |
| openclaw-ops | 待评估 | workflow skill |

### 条件二：文档覆盖目标用户场景

目标用户：个人开发者、小团队（2-10 人）、开源维护者、自托管服务维护者

| 场景 | 文档 | 状态 |
|------|------|------|
| 新用户入门 | getting-started/getting-started.md | 已有 |
| 理解架构 | getting-started/architecture-overview.md | 已有 |
| 接入第一台服务器 | tutorials/add-new-server.md | 已有 |
| 部署第一个应用 | tutorials/deploy-first-app.md | 已有 |
| 故障排查 | tutorials/troubleshoot-failed-deployment.md | 已有 |
| 协作协议 | AGENTS.md | 已有 |
| API/CLI 参考 | 待评估 | 待评估 |
| 常见问题 FAQ | 待评估 | 待评估 |

### 条件三：真实应用全生命周期验证

| 步骤 | 状态 | 说明 |
|------|------|------|
| 选择目标应用 | 已完成 | sub2api（WSL + prod0-main 双环境） |
| onboard 应用 | 已完成 | WSL + prod0-main 均已 onboard 进 catalog |
| 构建和部署 | 已完成 | WSL: compose up; prod0-main: candidate precheck + cutover |
| 验证和证据 | 已完成 | health check 通过，operation ledger 已记录 |
| 文档化过程 | 进行中 | 遇到并修复了 catalog repo_root 和 WSL 路径转换问题 |

---

## 📋 分支任务

临时任务，完成后必须回归主线。每个分支任务必须标注它服务的主线条件。

| ID | 任务 | 状态 | 服务主线条件 | 说明 |
|----|------|------|--------------|------|
| B1 | 1Panel 最新适配与扩展功能规划 | 进行中 | 条件二、Beta M5 Provider 合同 | 已建立 [1Panel 更新适配与扩展规划](onepanel-adaptation-expansion-plan.md)，M1 Provider 更新门禁已完成：route fingerprint、route diff 影响矩阵、object API contract fixture、health-check opt-in 集成；M2 只读能力扩展已完成：`service verify` compose identity label、`ingress verify` SSL 证书详情与 OpenResty 状态、`infra automation verify` cronjob 执行记录、`infra network firewall-audit` 防火墙规则漂移；M3 可变更能力扩展已完成：`infra network firewall plan/apply`、`infra automation plan/apply`、`ingress plan/apply`，所有 apply 后触发 verify 并记录 operation ledger；M4 App resource 与 1Panel 应用纳管已完成：`app object discover` 发现未纳管 1Panel 已安装应用，`app resource verify` 已扩展 live provider 数据库证据（可选，provider 不可达时跳过），ProviderGateway 新增 installed apps 和 databases 搜索能力；M5 观测与告警已完成：`infra health` 命令输出结构化健康摘要，新增 dashboard/alert/monitor API helpers 和 ProviderGateway 方法。 |

---

## 📦 Backlog

暂不执行的想法和需求，等待评估后决定是否纳入主线。

当前无 backlog 条目。

---

## 📌 使用规则

### 人类使用方式

- 用自然语言表达需求，不需要关心任务分类
- AI 会自动判断需求归属（主线/分支/backlog）
- 随时可以插入新想法，AI 会合理收敛

### AI 使用方式

1. **会话开始**：读取本文，确认主线位置，向人类报告当前进度
2. **收到需求**：判断归属
   - 直接服务主线条件 → 合入主线
   - 间接相关 → 创建分支任务，标注回归条件
   - 完全无关 → 记录到 backlog，询问是否现在做
3. **会话结束**：更新本文，标记完成项，记录进度

### 判断标准

- **主线**：不做这个，"首次运行闭环"目标就无法达成
- **分支**：做了有帮助，但不是当前阶段的必要条件
- **backlog**：有价值，但当前阶段不需要

---

## 关联文档

- [路线图](../strategy/roadmap.md) — 三阶段路线
- [愿景](../strategy/vision.md) — 项目愿景和目标用户
