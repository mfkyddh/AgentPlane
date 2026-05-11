---
status: active
owner: AgentPlane maintainers
last_verified: 2026-05-09
audience: both
---

# 进度追踪器

> 连接 [路线图](docs/core/roadmap.md)（往哪走）和日常工作（当前做什么）。

---

## 当前阶段目标

**开源用户单 checkout 后，能让 AI 通过 Skill 完成首次运行闭环。**

---

## 主线条件

> 必须全部满足，才能达成阶段目标。

| # | 条件 | 状态 | 说明 |
|---|------|------|------|
| C1 | 核心 Skill 测试覆盖 | ✓ 完成 | 16 个 Skill 已评估：13 高覆盖，2 中覆盖，1 低覆盖（toolchain-setup），2 无 CLI 命令。测试覆盖率 56.52%，870 tests passed |
| C2 | 文档覆盖目标用户场景 | ✓ 完成 | 5 份核心文档已重写 |
| C3 | 真实应用全生命周期验证 | ✓ 完成 | sub2api 双环境验证通过，文档化已完成 |

---

## 分支任务

> 临时任务，完成后必须回归主线。每个任务标注服务的主线条件。

| ID | 任务 | 状态 | 服务 | 说明 |
|----|------|------|------|------|
| B1 | 1Panel 适配与扩展 | 进行中 | C2 | M1-M5 已完成，详见 git log |
| B2 | complete sub2api dual-environment verification runbook | 已完成 | — | 2fd8711 (2026-05-08) |
| B3 | Phase A - 测试基础设施标准化 | 已完成 | — | 8c9aa4b (2026-05-08) |
| B4 | extract shared fake script templates (Phase B3) | 已完成 | — | 0205217 (2026-05-08) |
| B5 | add subdirectory conftest.py fixtures (Phase B4) | 已完成 | — | dc1563e (2026-05-08) |
| B6 | split test_app_delivery.py into 7 files (Phase B1) | 已完成 | — | 280275d (2026-05-08) |
| B7 | split remaining large test files (Phase B2) | 已完成 | — | c3ac009 (2026-05-08) |
| B8 | Phase C-D - PROGRESS 更新 + 并行优化 | 已完成 | — | c9eaec7 (2026-05-08) |
| B9 | codify test standards and add health check automation | 已完成 | — | 08aecd4 (2026-05-08) |
| B10 | extract duplicate helpers to shared modules (P1) | 已完成 | — | 929a857 (2026-05-08) |
| B11 | split 18 oversized test files into 42 focused files (P2) | 已完成 | — | 722d10e (2026-05-09) |
| B12 | migrate hardcoded IP/domain values to shared constants (P3) | 已完成 | — | 0156883 (2026-05-09) |
| B13 | update PROGRESS.md with P1-P3 completion and coverage stats | 已完成 | — | 50ada43 (2026-05-09) |
| B14 | add .omc/ to gitignore, remove stale GStack docs, update progress | 已完成 | — | ae15c22 (2026-05-09) |
| B15 | auto-log B14 from post-commit hook | 已完成 | — | c599b1b (2026-05-09) |
| B16 | auto-log B14 from post-commit hook | 已完成 | — | a38f42b (2026-05-09) |
| B17 | remove all gstack remnants | 已完成 | — | 930a147 (2026-05-09) |
| B18 | Alpha exit: lint 清零 + web/onepanel/ssh 测试覆盖提升 | 已完成 | C1 | 870 tests, 56.52% coverage, ruff 0 errors |
| B19 | Alpha exit — lint 清零 + 128 new tests + coverage提升 | 已完成 | — | 4738a2a (2026-05-09) |
| B20 | Phase 1 execution chain optimization | 已完成 | — | 49795f9 (2026-05-09) |
| B21 | Phase 2+3 — streaming docker transfer, error structuring, ADRs | 已完成 | — | eccd659 (2026-05-09) |
| B22 | verify prepare-commit-msg auto-stages PROGRESS.md | 已完成 | — | pending (2026-05-09) |
| B23 | debug prepare-commit-msg execution | 已完成 | — | pending (2026-05-09) |
| B24 | clean up test marker file | 已完成 | — | pending (2026-05-09) |
| B25 | foundation-replan Phase 2.1: Provider Protocol + adapter + stub | 已完成 | — | protocol.py (13 methods), onepanel_adapter.py, stub_provider.py, 28 contract tests |
| B26 | foundation-replan Phase 2.2: Projection contract tests | 已完成 | — | 10 projection tests (idempotency, shape, consistency) |
| B27 | foundation-replan Phase 3.1: Golden test system | 已完成 | — | pytest -m golden, 9 tests, 1.27s |
| B28 | foundation-replan Phase 3.2: Doc-code alignment | 已完成 | — | architecture.md updated, 7 doc-contract tests |
| B29 | foundation-replan Phase 3.3: CLI consistency | 已完成 | — | 5 CLI registration tests |
| B30 | foundation-replan Phase 2-3 — provider abstraction, projection contracts, golden tests, doc alignment | 已完成 | — | pending (2026-05-09) |
| B31 | correct commit_message module path in CI workflow | 已完成 | — | pending (2026-05-09) |
| B32 | replace 'repo' with 'project' subcommand in CI workflow | 已完成 | — | pending (2026-05-09) |
| B33 | fix docs-sanity gate errors — archive status, broken links, isolated doc | 已完成 | — | pending (2026-05-09) |
| B34 | foundation-replan Phase 0-1 — boundary repair and SSH Protocol | 已完成 | — | pending (2026-05-09) |
| B35 | add resource topology view and design system | 已完成 | — | pending (2026-05-10) |
| B36 | WebUI component refactoring, i18n, dashboard optimization, and E2E test suite | 已完成 | — | pending (2026-05-11) |
| B37 | Beta M1: 公开贡献者循环 | 已完成 | — | Issue/PR 模板、CONTRIBUTING.md 跨平台指南、CI fork PR 配置文档 |
| B38 | Beta M2: 发布工程 | 已完成 | — | release.yml 工作流、版本号对齐、coverage 门禁提升到 50% |
| B39 | Beta M3: 合同硬化 | 已完成 | — | schema 移至正式位置、独立验证模式、validate-contract CLI、v1→v2 迁移文档、contract 模板 |
| B40 | Beta M1/M2/M3 — contributor loop, release engineering, contract hardening | 已完成 | — | pending (2026-05-11) |
| B41 | fix flaky web async tests with pytest-rerunfailures | 已完成 | — | pending (2026-05-11) |

---

## 想法池

> 未经评估的灵感、需求、问题。定期清理：转为分支任务或丢弃。

| ID | 想法 | 来源 | 日期 | 处置 |
|----|------|------|------|------|
| — | （暂无） | — | — | — |

---

## 完成归档

> 已完成的重要工作，按时间倒序。保留上下文，不占主视图。

| ID | 任务 | 完成日期 | 服务 | 关键成果 |
|----|------|----------|------|----------|
| B8 | 测试体系重构 | 2026-05-08 | C1 | Phase A-D：常量池、覆盖率阈值、风格指南、fake 脚本提取、conftest、大文件拆分（3189 行→7 文件）、755 tests passed, 28.76% coverage。P1-P3 追加：消除重复 helper、拆分 18 个超大文件为 42 个、硬编码常量迁移、742 tests passed, 54.34% coverage |
| B3 | agentplane-infra-ops 测试覆盖 | 2026-05-08 | C1 | 13 tests，覆盖 automation/local/network 命令，7485c54 |
| B2 | 5 域模型重构完成 | 2026-05-08 | C1 | 4 文件迁移到 domain/infra/，100% 完成，1f0e670 |
| B6 | optimize CLAUDE.md and AGENTS.md | 2026-05-08 | — | e460e17 |
| B5 | add session init rule to read AGENTS.md | 2026-05-08 | — | 749059d |
| B4 | add mandatory thinking transparency rule | 2026-05-08 | — | a8e458d |
| B3 | git post-commit hook 自动记录进度 | 2026-05-08 | — | 每次 commit 自动追加进度 |
| — | sub2api 双环境验证文档化 | 2026-05-08 | C3 | runbook 模板，docs/runbooks/sub2api-dual-env-verification.md |
| B2 | 5 域模型重构 | 2026-05-07 | C1 | 70 文件，3379+/3817-。Layer 0-3 对齐，infra 域从 cli/ 迁移到 domain/，app 域移除 wrapper，87 测试修复，742 passed |
| — | 文档体系重构 | 2026-05-07 | C2 | 80+ 文件 → ~20 活跃文档。3 层模型，核心文档重写（愿景/原则/路线图/架构），5 份用户文档 |
| — | WebUI 初始版本 | 2026-05-06 | — | dashboard + REST API + agent chat，9bed54e |

---

## 实验记录

> 人机协作实验，独立追踪。记录人类输入、AI 执行、结果、发现。

### 实验 #1 — site-migration-ops 完整闭环

**目标**：用一句话让 AI 完成一次 site-migration-ops 的完整执行，人类只在开始和结束时介入。

**验收**：AI 跑完 plan → apply → verify → ledger 全流程，人类中途确认次数 ≤ 3。

**状态**：✓ 完成

| 日期 | 人类输入 | AI 执行步骤 | 结果 | 介入次数 | 发现 |
|------|---------|------------|------|---------|------|
| 2026-05-07 | "启动" | ① 跑测试 23/23 ② search ingress ③ verify 失败→修复编码 bug ④ verify 失败→重构为本地签名+SSH ⑤ verify 成功 | 成功 | 0 | 测试用 mock 不暴露平台问题；真实验证发现架构缺陷并修复 |

**关键发现**：
1. 测试全绿但全部 mock，不连真实 API
2. Windows gbk 编码问题（4 处 subprocess.run）
3. 远程脚本依赖架构缺陷 → 重构为本地签名+SSH 内联执行

---

## 状态说明

| 状态 | 含义 |
|------|------|
| 待开始 | 尚未评估或启动 |
| 进行中 | 正在执行 |
| 收尾中 | 主体完成，待验证或文档化 |
| ✓ 完成 | 全部完成并验证 |
| 搁置 | 暂停，有明确原因 |

---

## 关联文档

- [路线图](docs/core/roadmap.md) — Alpha → Beta → GA 大方向
- [愿景](docs/core/vision.md) — 项目定位、目标用户
- [编码与协作规范](docs/conventions.md) — 协作协议
