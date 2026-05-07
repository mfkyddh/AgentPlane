---
status: active
owner: AgentPlane maintainers
last_verified: 2026-05-07
superseded_by: null
audience: both
---

# Changelog

里程碑记录。详细变更见 `git log`。

## 0.2.0 — 2026-05-07

- 文档体系重构：80+ 文件精简到 ~20 个活跃文档
- 新增 WebUI（FastAPI + Vue 3 CDN）
- 新增统一架构文档、技术栈文档、命令参考
- 职责边界重构：AGENTS.md（AI 规则）/ CLAUDE.md（Claude 特有）/ conventions.md（共用规范）三文件分离
- 启动人机协作实验框架：backlog.md 新增实验记录板块

## 0.1.0 — 2026-04-29

Initial alpha baseline.

- CLI-first 仓库治理：`agentplane repo health-check`、`agentplane repo release-check`
- 离线默认测试门禁，显式标记 live WSL/SSH/Docker/provider 检查
- Secrets 分离设计，secrets/ 被 .gitignore 保护
- 18 个 Skill 覆盖 infra/service/app/ingress 场景
