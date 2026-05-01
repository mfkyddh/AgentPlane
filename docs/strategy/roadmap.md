---
status: active
owner: AgentPlane maintainers
last_verified: 2026-05-01
audience: both
---

# 路线图

结论：从 Alpha 到"小团队标准工具"分三个阶段推进。每个阶段有明确的完成标准，通过实践验证而非计划驱动。

---

## 三阶段路线

```
Alpha（当前）          Beta                   GA
─────────────────────────────────────────────────────→
  夯实核心             开放验证               规模扩展

  • CLI 骨架稳定       • 外部用户可用         • 100+ 用户
  • 文档体系完整       • Provider 合同稳定    • 社区自运转
  • 离线测试覆盖       • App delivery 成熟    • 插件生态
```

---

## 当前状态：Alpha

### 已稳定可依赖

- 仓库治理（`repo health-check`、`release-check`）
- CLI 入口纪律（正式操作通过 `agentplane ...`）
- 离线测试门禁、文档治理、Secret 边界

### 仍在收敛

- 公开安装体验（发布产物未自动化）
- Provider 合同（合同测试待扩展）
- App delivery schema（schema_version: 2 仍在扩展）
- Live gate（需要准备环境）

### Alpha 完成标准

- [ ] 所有核心 Skill 有完整测试
- [ ] 文档体系覆盖所有目标用户场景
- [ ] 至少一个真实应用完成全生命周期验证

---

## Beta 关键里程碑

| 里程碑 | 目的 |
|--------|------|
| M1: 公开贡献者循环 | 外部 PR 可自验证 |
| M2: 发布工程 | tag 可复现 |
| M3: 合同硬化 | 交付合同可机器检查 |
| M4: 运行时拆分 | 降低风险 |
| M5: Provider 合同 | provider 细节隔离 |

---

## 核心原则

- **Skill 路由，CLI 执行** — Skill 是 Agent 理解意图的入口，正式动作回到 `agentplane ...`
- **证据优先** — 没有证据的正式操作不算完成
- **Dogfooding** — AgentPlane 必须首先管理自己

---

## 关联文档

- [愿景](vision.md) — 项目定位
- [原则](principles.md) — 哲学和工程原则
- [主线追踪器](../project/backlog.md) — 当前任务进度
