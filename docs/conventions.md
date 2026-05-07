---
status: active
owner: AgentPlane maintainers
last_verified: 2026-05-07
superseded_by: null
audience: both
---

# 编码与协作规范

> AI 和人类共用的行为准则。AGENTS.md 和 CLAUDE.md 引用本文，不重复维护。

---

## 编码行为准则

基于 [Karpathy Guidelines](https://x.com/karpathy/status/2015883857489522876)，减少常见 LLM 编码错误。

### 1. 先思考再编码

- 明确假设；不确定就问，不要猜测
- 有多种解释时全部列出，不要默默选一种
- 有更简单方案时主动提出；遇到不清楚的地方停下来，说明哪里不确定

### 2. 简洁优先

- 最少代码解决问题；不加未要求的功能
- 单次使用的代码不做抽象
- 不加没被要求的"灵活性"或"可配置性"
- 不为不可能的场景写错误处理
- 200 行能缩到 50 行就重写

### 3. 精准改动

- 只改必须改的；不"顺手改进"相邻代码
- 匹配现有风格，即使你会写得不同
- 发现无关死代码只提醒，不删除
- 只清理自己改动造成的孤儿代码

### 4. 目标驱动执行

- 把任务转化为可验证的目标："加验证" → "写测试然后让它通过"
- 多步任务先列计划：`步骤 → 验证方式`
- 强成功标准让 AI 能独立循环；弱标准（"让它能跑"）需要反复确认

---

## 求是 Skills 使用原则

在以下场景必须主动调用对应的 qiushi-skill：

| 场景 | 调用的 Skill | 触发信号 |
|------|-------------|---------|
| 做重大判断或决策前 | `qiushi-skill:investigation-first` | 信息不足、需要先摸清现状 |
| 面对复杂问题不知从何入手 | `qiushi-skill:contradiction-analysis` | 多个因素冲突、主次不清 |
| 完成阶段性工作后 | `qiushi-skill:criticism-self-criticism` | 阶段验收、需要审查质量 |
| 面对长期复杂任务 | `qiushi-skill:protracted-strategy` | 无法速胜、需要分阶段推进 |
| 多个任务争夺注意力 | `qiushi-skill:concentrate-forces` | 优先级过多、资源紧张 |
| 需要收集多方意见 | `qiushi-skill:mass-line` | 需要整合多源信息 |
| 从零起步、资源有限 | `qiushi-skill:spark-prairie-fire` | bootstrap、MVP、小团队起步 |
| 多个目标需要平衡 | `qiushi-skill:overall-planning` | trade-offs、目标冲突 |
| 提出方案需要验证 | `qiushi-skill:practice-cognition` | experiment、prototype、validate |

优先原则：先用 `实事求是` 约束判断，再在明确适用时调用下游 skill。

---

## 哲学原则

不需要显式调用 skill，但在对应场景中主动应用：

- **第一性原理** — 架构设计时从基本事实出发
- **奥卡姆剃刀** — 如无必要，勿增实体
- **费曼学习法** — 用简单语言解释复杂概念
- **苏格拉底式提问** — 通过提问引导思考，而非直接给答案
- **YAGNI** — 只实现当前需要的功能
- **DRY** — 消除重复代码
- **KISS** — 保持简单
- **SOLID** — 遵循职责单一、开闭原则等

---

## 反模式

| 错误做法 | 正确做法 |
|----------|----------|
| `scripts/` 当入口 | `agentplane ...` |
| Skill 拼 SSH/Docker | 走 CLI |
| 多层 `ssh bash -c` | `infra remote bash` |
| 大批量单提交 | 按逻辑拆分 |
| 格式混功能 | 独立提交 |
| 平台变种 venv | 只用根 `.venv` |

---

## 协作协议

**人类表达意图，AI 自主推进，所有工作回归主线。**

- **会话开始**：读取 `backlog.md`，确认主线进度，向人类报告当前位置
- **收到需求**：判断归属
  - 直接服务主线（当前阶段目标）→ 合入主线，立即执行
  - 间接相关 → 创建分支任务，完成后回归主线
  - 完全无关 → 记录到 backlog，询问是否现在做
- **会话结束**：更新 `backlog.md`，标记完成项，记录进度

---

## 关联文档

- [AGENTS.md](../AGENTS.md) — AI 工作规范（引用本文）
- [CLAUDE.md](../CLAUDE.md) — Claude 特有指令（引用本文）
- [架构](architecture.md) — 技术架构
- [技术栈](tech-stack.md) — 技术选型与约束
