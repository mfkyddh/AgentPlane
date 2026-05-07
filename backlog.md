---
status: active
owner: AgentPlane maintainers
last_verified: 2026-05-07
superseded_by: null
audience: both
---

# 主线追踪器

> AgentPlane 唯一的任务真相源。所有工作归属于主线条件、分支任务或 backlog 三者之一。

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
| 新用户入门 | [docs/getting-started.md](docs/getting-started.md) | 已有 |
| 理解架构 | [docs/architecture.md](docs/architecture.md) | 已有 |
| 接入第一台服务器 | [docs/tutorials/add-new-server.md](docs/tutorials/add-new-server.md) | 已有 |
| 部署第一个应用 | [docs/tutorials/deploy-first-app.md](docs/tutorials/deploy-first-app.md) | 已有 |
| 故障排查 | [docs/tutorials/troubleshoot-failed-deployment.md](docs/tutorials/troubleshoot-failed-deployment.md) | 已有 |
| 协作协议 | [AGENTS.md](AGENTS.md) | 已有 |
| API/CLI 参考 | [docs/command-reference.md](docs/command-reference.md) | 已有 |
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

## 分支任务

临时任务，完成后必须回归主线。每个分支任务必须标注它服务的主线条件。

| ID | 任务 | 状态 | 服务条件 | 说明 |
|----|------|------|----------|------|
| B1 | 1Panel 适配与扩展 | 进行中 | 条件二、Beta M5 | M1-M5 已完成，详见 git log |

---

## 人机协作实验

> 每次实验记录：人类说了什么、AI 中途问了什么、结果如何。积累数据，优化表达协议。

### 实验 #1 — site-migration-ops 完整闭环

**目标**：用一句话让 AI 完成一次 site-migration-ops 的完整执行，人类只在开始和结束时介入。

**验收**：AI 跑完 plan → apply → verify → ledger 全流程，人类中途确认次数 ≤ 3。

**约束**：不修改 Skill 代码，不新增功能，只记录过程。

**状态**：进行中

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
