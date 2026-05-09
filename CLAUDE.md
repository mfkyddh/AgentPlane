# CLAUDE.md

> 本文档是 Claude Code 专属指令。通用 AI 规则见 [AGENTS.md](AGENTS.md)。
> 编码行为准则、哲学原则、求是 Skills 见 [docs/conventions.md](docs/conventions.md)。

## 会话初始化

每次会话开始时，先读 [AGENTS.md](AGENTS.md) 中的规则，再开始工作。

## 关键文档

| 文档 | 用途 |
|------|------|
| [docs/core/architecture.md](docs/core/architecture.md) | 架构、域、投影模型、CLI 接口 |
| [docs/command-reference.md](docs/command-reference.md) | CLI 命令参考 |
| [docs/getting-started.md](docs/getting-started.md) | 5 分钟上手 |
| [docs/conventions.md](docs/conventions.md) | 技术栈、编码规则、协作规范 |
| [docs/core/principles.md](docs/core/principles.md) | 道法术三层原则体系 |
| [docs/maintainer-guide.md](docs/maintainer-guide.md) | 治理资产约束、Skill 同步门禁 |

## Skill 路由

当用户请求匹配可用 skill 时，通过 Skill 工具调用。不确定时，也调用。

| 场景 | Skill |
|------|-------|
| 产品想法/头脑风暴 | /office-hours |
| 策略/范围 | /plan-ceo-review |
| 架构 | /plan-eng-review |
| 设计 | /design-consultation 或 /plan-design-review |
| 完整审查 | /autoplan |
| Bug/错误 | /investigate |
| QA/测试 | /qa 或 /qa-only |
| 代码审查 | /review |
| 视觉打磨 | /design-review |
| 发布/部署 | /ship 或 /land-and-deploy |

领域 Skill（`.agents/skills/`）：agentplane-infra-ops、agentplane-app-ops、agentplane-service-ops、agentplane-ingress-ops、agentplane-projection-ops、agentplane-project-ops、app-delivery-ops、site-migration-ops 等。完整列表见 `.agents/skills/` 目录。

## 思维透明（强制）

**每次思考时，必须同步告知用户你使用了哪些 skill 和哪些哲学思想。**

输出格式（在回复开头或关键决策点）：

```
🧠 思维过程
- Skill: [使用的 skill，无则写"无"]
- 哲学: [应用的思想，无则写"无"]
- 理由: [为什么选择这些 skill/思想，一句话]
```

可用的哲学思想见 [docs/core/principles.md](docs/core/principles.md)（道法术三层）。不限于项目中列出的，用到其他思想也要说明。

## PROGRESS.md 维护

git post-commit hook 会自动将每次 commit 追加到 PROGRESS.md 的分支任务表。此外：

- **重要工作完成后**（重构、新功能、关键修复），手动更新 PROGRESS.md 对应条目的状态和说明
- **分支任务完成时**，将状态改为"已完成"
- **新阶段开始时**，在主线条件表中更新状态
- commit message 使用 conventional commits 前缀（feat/fix/refactor/docs/test/chore）以触发 hook
