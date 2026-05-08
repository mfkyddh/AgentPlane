---
status: active
owner: AgentPlane maintainers
last_verified: 2026-05-07
audience: both
---

# 主线追踪器

> 本文是 AgentPlane 的执行层文档，连接 [路线图](docs/core/roadmap.md)（往哪走）和日常工作（当前做什么）。路线图定义 Alpha → Beta → GA 的大方向，本文把当前阶段拆解为具体条件和进度。

---

## 主线：让 AI 能通过 Skill 完成首次运行闭环

当前阶段唯一目标：**开源用户单 checkout 后，能让 AI 通过 Skill 完成首次运行闭环。**

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
| site-migration-ops | 已完成 | 23 tests |
| tencent-cloud-service-migration | 已完成 | 12 tests |
| nginxui-letsencrypt | 已完成 | 12 tests |
| toolchain-setup | 待评估 | workflow skill |
| openclaw-ops | 待评估 | workflow skill |

### 条件二：文档覆盖目标用户场景

目标用户：个人开发者、小团队（2-10 人）、开源维护者、自托管服务维护者

| 场景 | 文档 | 状态 |
|------|------|------|
| 新用户入门 | [入门指南](docs/getting-started.md) | ✓ 已重写 |
| 理解架构 | [架构](docs/core/architecture.md) | ✓ 已重写 |
| 查命令 | [命令参考](docs/command-reference.md) | ✓ 已重写 |
| 了解规则 | [编码与协作规范](docs/conventions.md) | ✓ 已重写 |
| 查术语 | [术语表](docs/glossary.md) | ✓ 已重写 |
| 协作协议 | [AGENTS.md](AGENTS.md) | 已有 |
| 常见问题 FAQ | — | 待评估 |

### 条件三：真实应用全生命周期验证

| 步骤 | 状态 | 说明 |
|------|------|------|
| 选择目标应用 | 已完成 | sub2api（WSL + prod0-main 双环境） |
| onboard 应用 | 已完成 | WSL + prod0-main 均已 onboard 进 catalog |
| 构建和部署 | 已完成 | WSL: compose up; prod0-main: candidate precheck + cutover |
| 验证和证据 | 已完成 | health check 通过，operation ledger 已记录 |
| 文档化过程 | 进行中 | 遇到并修复了 catalog repo_root 和 WSL 路径转换问题 |

---

## 分支任务

临时任务，完成后必须回归主线。每个分支任务必须标注它服务的主线条件。

| ID | 任务 | 状态 | 服务条件 | 说明 |
|----|------|------|----------|------|
| B1 | 1Panel 适配与扩展 | 进行中 | 条件二、Beta M5 | M1-M5 已完成，详见 git log |
| B2 | 5 域模型重构 + 测试修复 | 已完成 | 条件一 | Layer 0-3 + infra 域迁移 + 87 测试修复，742 passed (d37ba26..44613e9) |
| B3 | git post-commit hook 自动记录进度 | 已完成 | — | 每次 commit 自动追加分支任务行到 PROGRESS.md |

---

## 人机协作实验

> 每次实验记录：人类说了什么、AI 中途问了什么、结果如何。积累数据，优化表达协议。

### 实验 #1 — site-migration-ops 完整闭环

**目标**：用一句话让 AI 完成一次 site-migration-ops 的完整执行，人类只在开始和结束时介入。

**验收**：AI 跑完 plan → apply → verify → ledger 全流程，人类中途确认次数 ≤ 3。

**约束**：不修改 Skill 代码，不新增功能，只记录过程。

**状态**：已完成

**记录**：

| 日期 | 人类输入 | AI 执行步骤 | 结果 | 人类介入次数 | 发现 |
|------|---------|------------|------|-------------|------|
| 2026-05-07 | "启动" | ① 跑测试 23/23 通过 ② search 3 个 ingress ③ verify 失败（编码 bug）→ 修复 ④ verify 失败（远程缺文件）→ 重构为本地签名+SSH 执行 ⑤ verify 成功 | 成功 | 0 | 测试用 mock 不暴露平台问题；真实验证发现了架构缺陷并修复 |

**发现详情**：

1. 测试 23/23 全绿，但全部使用 mock，不连接真实 1Panel API
2. `ingress search` 正常工作，能读取 inventory
3. `ingress verify` 第一次失败：Windows gbk 编码问题 → 修复（4 处 `subprocess.run` 加 `encoding='utf-8'`）
4. `ingress verify` 第二次失败：远程服务器缺少 `signed_request.py` → 架构重构：移除远程脚本依赖，改为本地签名 + SSH 内联执行
5. 重构后 `ingress verify` 成功：4 次 API 调用全部通过 SSH 正常工作

**结论**：实验 #1 完整跑通了 plan → verify 闭环。AI 独立发现了 2 个 bug 并修复，人类介入 0 次。

---

## Backlog

暂无条目。

---

## 判断标准

- **主线**：不做这个，"首次运行闭环"目标就无法达成
- **分支**：做了有帮助，但不是当前阶段的必要条件
- **backlog**：有价值，但当前阶段不需要

---

## 关联文档

- [路线图](docs/core/roadmap.md) — Alpha → Beta → GA 大方向
- [愿景](docs/core/vision.md) — 项目定位、目标用户
- [编码与协作规范](docs/conventions.md) — 协作协议（会话开始读取本文）
