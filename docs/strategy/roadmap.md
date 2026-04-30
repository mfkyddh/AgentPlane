---
status: active
owner: AgentPlane maintainers
last_verified: 2026-04-30
superseded_by: null
audience: human
layer: strategy
---

# 🗺️ AgentPlane 路线图

结论：从 Alpha 到"小团队标准工具"分三个阶段推进。每个阶段有明确的里程碑和完成标准，通过实践验证而非计划驱动。

---

## 🎯 一句话目标

**3 年内成为小团队的标准工具，拥有 100+ 用户**

---

## ✅ 当前状态

### 已稳定可依赖

| 领域 | 当前状态 |
|------|----------|
| 仓库治理 | `agentplane repo health-check` 和 `release-check` 覆盖 lint、测试、secret 扫描、隐私扫描和文档完整性 |
| CLI 入口纪律 | 正式操作通过 `agentplane ...` 路由；直接脚本只是实现细节 |
| 离线测试门禁 | 默认测试设计为确定性和离线 |
| 文档治理 | Active 文档有 frontmatter、索引和完整性检查 |
| Secret 边界 | 真实 secret 只在被忽略的 `secrets/` 中；示例放在 `templates/` 下 |

### 仍在收敛

| 领域 | 仍处于 Alpha 的原因 |
|------|---------------------|
| 公开安装体验 | 项目可从源码使用，但发布产物和包发布尚未自动化 |
| Provider 合同 | Provider/debug 层在成为稳定公开 API 前需要更多合同测试 |
| App delivery schema | `schema_version: 2` 是正式路径，但机器可读 schema 和迁移说明仍在扩展中 |
| Live gate | WSL、SSH、Docker、DNS 和 provider 检查需要明确准备的环境 |

---

## 🗺️ 三阶段路线

```
Alpha（当前）          Beta                   GA
─────────────────────────────────────────────────────→
  夯实核心             开放验证               规模扩展

  • CLI 骨架稳定       • 外部用户可用         • 100+ 用户
  • 文档体系完整       • Provider 合同稳定    • 社区自运转
  • 离线测试覆盖       • App delivery 成熟    • 插件生态
  • 投影模型验证       • 真实场景验证         • 标准工具定位
```

---

## 🏗️ 阶段一：Alpha（当前）

**目标**：夯实核心，确保基础可靠

**已完成**：
- P0-P7 阶段（蓝图、证据模型、项目模型、生命周期验证）
- 仓库治理、离线测试、文档治理、secrets 边界
- CLI 入口纪律、投影模型、Skill 路由

**当前重点**：
- 完善核心 Skill 覆盖
- 建立文档体系
- 验证产品价值

**完成标准**：
- [ ] 所有核心 Skill 有完整测试
- [ ] 文档体系覆盖所有目标用户场景
- [ ] 至少一个真实应用完成全生命周期验证

---

## 🚀 阶段二：Beta

**目标**：开放验证，让外部用户可用

**关键里程碑**：

| 里程碑 | 目的 | 完成标准 | 进度 |
|--------|------|----------|------|
| M1: 公开贡献者循环 | 外部 PR 可自验证 | CI 完善，issue 模板存在 | **部分完成** |
| M2: 发布工程 | tag 可复现 | `uv build` 通过，release notes 自动化 | **部分完成** |
| M3: 合同硬化 | 交付合同可机器检查 | JSON Schema 存在，错误码稳定 | 待定 |
| M4: 运行时拆分 | 降低风险 | 职责清晰分离 | 待定 |
| M5: Provider 合同 | provider 细节隔离 | 合同测试覆盖 | 待定 |

**完成标准**：
- [ ] 至少 10 个外部用户成功使用
- [ ] Provider 合同稳定
- [ ] App delivery schema 正式发布

---

## 🌍 阶段三：GA

**目标**：规模扩展，成为小团队标准工具

**关键方向**：
- 插件生态：支持第三方 Skill 和 Provider
- 社区建设：文档、教程、案例
- 标准定位：成为小团队 AI-assisted 运维的默认选择

**完成标准**：
- [ ] 100+ 活跃用户
- [ ] 社区自运转（外部贡献者维护）
- [ ] 至少 3 个成功案例文档化

---

## 📋 P0-P7 阶段推进

| 阶段 | 名称 | 目标 | 状态 |
|------|------|------|------|
| P0 | 蓝图落库与任务机制建立 | 把蓝图、阶段工作计划和继续执行协议纳入 active docs | **已完成** |
| P1 | 任务书与"继续执行"闭环稳定 | 让 Agent 能根据任务书恢复上下文、定位下一步并回写状态 | **已完成** |
| P2 | 操作凭证、例外和复盘模型 | 建立 Operation Receipt、Exception Review 和最小证据规范 | **已完成** |
| P3 | 项目注册表与项目蓝图模型 | 区分 project registry、app catalog 和 blueprint，定义最小字段 | **已完成** |
| P4 | 应用生命周期示范闭环 | 选择低风险示范项目跑通接入、变更、验证、回写、退役口径 | **已完成** |
| P5 | 可视化控制面增强 | 将阶段、项目、任务、风险和证据接入 `repo status` 或静态面板 | **已完成** |
| P6 | 安全、并发与多 Agent 受控扩展 | 补充威胁模型、锁机制、阶段审批和多 Agent 协作边界 | **已完成** |
| P7 | 应用生命周期真实验证 | 用真实 app 跑通 onboard → verify → receipt → offboard 完整链路 | **已完成** |

---

## 📌 核心原则

### Skill 路由，CLI 执行

Skill 是 Agent 理解人类意图的入口，负责触发、路由、边界提示和验证提醒；正式动作必须回到 `agentplane ...`。

### 人类阶段门

每个阶段开始前必须先和人类讨论三件事：具体实施方向、技术采用、概念边界。只有这三项被确认后，才能把阶段拆成具体任务。

### 证据优先

没有证据的正式操作，不算完成。证据分层：原始输出（排查）→ Operation Receipt（结构化摘要）→ 异常复盘（学习材料）→ 趋势报告（改进方向）。

### 渐进控制

项目不必一次性完全进入 AgentPlane。建议长期保留接入等级：Level 0（未接入）→ Level 1（登记接入）→ Level 2（规范检查）→ Level 3（部署运维）→ Level 4（完整生命周期）。

### Dogfooding

AgentPlane 必须首先管理自己。任何对外声称可复用的能力，优先在 AgentPlane 仓库自己的文档、Skill、测试、状态面板和任务书中跑通。

---

## 🔧 长期机制

### Operation Receipt

每次正式任务的人类可读摘要。最小字段：operation_id、goal、skill、commands、verification、artifacts、follow_up。

### Exception Review

异常复盘记录失败、紧急绕过、回滚和审批拒绝。目标不是追责，而是把问题转化为更好的 Skill、规范、测试或证据。

### Project Registry

项目注册表是比 app catalog 更上层的项目视图，覆盖 AgentPlane 自身、应用仓库、文档站、服务组件和示范项目。

### Status Dashboard

`agentplane repo status` 是第一版控制面状态面板。后续可逐步增加阶段状态、任务状态、Operation Receipt、项目注册表和风险摘要。

---

## 📊 成熟度判断

AgentPlane 从 alpha 走向 beta，不取决于 Skill 数量，而取决于这些闭环是否稳定：

1. 人类能用一句目标触发正确 Skill
2. Agent 能找到当前阶段和下一项任务
3. 正式动作能产生验证和证据
4. 任务完成状态能回写到工作计划
5. 异常能进入复盘并转化为长期资产
6. 项目接入和退役都能走同一套生命周期口径
7. 状态面板能帮助人类判断下一步

---

## 🔗 关联文档

- [愿景](vision.md) — 我们要去哪里
- [原则](principles.md) — 我们如何思考
- [阶段工作计划](../maintainers/agentplane-roadmap-workbook.md) — 任务推进真源
- [控制面合同](../architecture/control-plane.md) — 正式执行合同
