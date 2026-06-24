---
status: active
owner: AgentPlane maintainers
last_verified: 2026-05-07
superseded_by: null
audience: both
---

# Changelog

里程碑记录。详细变更见 `git log`。

## 1.0.0 — 2026-06-24

**GA 正式发布**：从 Beta 到 Production/Stable 的里程碑。

### 核心成就

- **CLI 命令测试覆盖率 86%**：从 38% 提升到 86%，超过门禁 85%
- **Beta 退出标准全部满足**：源文件 < 500 行、ruff 0 errors、CLI 覆盖率 > 85%
- **测试套件稳定**：2290+ 测试通过，0 失败

### 测试覆盖提升

- runtime_deploy.py：42% → 91%（+49%）
- delivery_handlers_deploy.py：8% → 86%（+78%）
- delivery_handlers_candidate.py：27% → 92%（+65%）
- delivery_handlers_planning.py：39% → 95%（+56%）
- app.py CLI dispatch：58% → 90%（+32%）
- project_checks.py：39% → 92%（+53%）
- web.py CLI：31% → 100%（+69%）
- ingress.py CLI：47% → 100%（+53%）

### 新增测试文件

- tests/app/test_runtime_deploy.py（15 tests）
- tests/app/test_delivery_handlers_deploy.py（10 tests）
- tests/cli/test_app_cli.py（40 tests）
- tests/cli/test_project_helpers.py（44 tests）
- tests/cli/test_web_cli.py（9 tests）
- tests/cli/test_ingress_cli.py（21 tests）
- tests/cli/test_infra_handlers.py（13 tests）
- tests/cli/test_service.py（9 tests）

### 门禁升级

- 覆盖率门禁：44% → 85%
- 版本状态：Beta → Production/Stable

---

## 0.3.0 — 2026-06-11

- 质量加固：测试金字塔修正（57 文件 e2e→integration），测试分布 unit 72% / integration 29% / e2e 1%
- Provider 契约测试补全：+29 负面/边界测试，总计 73 契约测试
- 投影模型黄金测试：+8 三层投影格式验证测试
- CLI 一致性审计：+2 跨域 verb 一致性验证测试
- 运行时拆分设计：ADR 011，domain/app+service 迁移到 ProviderProtocol
- 真实验证 Runbook：基础设施服务、CLIProxyAPI、静态站点全生命周期验证模板
- Bug 修复：4 个预存在测试 bug（default_provider_gateway→get_provider）

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
