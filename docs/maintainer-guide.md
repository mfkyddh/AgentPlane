---
status: active
owner: AgentPlane maintainers
last_verified: 2026-05-07
audience: maintainer
---

# Maintainer 指南

> 本文档面向 AgentPlane 的维护者，说明治理资产的约束和协作规则。

---

## 治理资产闭环

| 资产 | 角色 | 约束 |
|---|---|---|
| 代码 | 定义正式能力 | 先有 CLI，再补周边 |
| 模板 | 沉淀稳定输入骨架 | 不承载一次性现场上下文 |
| skill | Agent 路由层 | 不变成第二实现 |
| 文档 | 长期合同与专题解释 | 架构页讲边界，runbook 讲流程 |
| 测试 | 回归与约束 | 冻结 CLI 合同 |

**为什么有这些约束？**
- 确保一致性：所有资产都遵循同一套规则
- 避免混乱：不会把不同职责的资产混在一起
- 易于维护：每个资产都有明确的职责

---

## Skill 同步门禁

任何改变正式行为的变更，都必须同步检查 `.agents/skills`。不得把"后续再补 skill"作为完成口径。

**为什么需要 Skill 同步门禁？**
- 确保一致性：Skill 和 CLI 保持同步
- 避免遗漏：不会忘记更新 Skill
- 提高质量：每次变更都经过完整检查

---

## 关联文档

- [架构](architecture.md) — 技术架构
- [编码与协作规范](conventions.md) — 编码行为准则
- [原则](principles.md) — 道法术三层原则体系
