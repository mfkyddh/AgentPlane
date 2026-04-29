---
status: active
owner: AgentPlane maintainers
last_verified: 2026-04-29
superseded_by: null
audience: both
---

# 路线图

AgentPlane 目前处于 Alpha 阶段，是一个 CLI-first 的控制面模板，用于 AI 辅助的基础设施运维。

## 🎯 战略蓝图

长期北极星计划在 [AgentPlane 终极蓝图 v4](docs/reference/agentplane-ultimate-blueprint.md) 中追踪。阶段执行状态在 [AgentPlane Roadmap Workbook](docs/maintainers/agentplane-roadmap-workbook.md) 中追踪。

P0-P7 阶段（蓝图落库、继续执行协议、证据模型、项目模型、生命周期示范设计、可视化面板、安全框架、生命周期验证）已完成。

这些文档不替代正式控制面合同。正式操作仍然通过 `agentplane ...` 路由，执行语义由 [控制面核心合同](docs/architecture/control-plane.md) 管辖。

## ✅ 已稳定可依赖

| 领域 | 当前状态 |
|------|----------|
| 仓库治理 | `agentplane repo health-check` 和 `release-check` 覆盖 lint、测试、secret 扫描、隐私扫描和文档完整性 |
| CLI 入口纪律 | 正式操作通过 `agentplane ...` 路由；直接脚本只是实现细节 |
| 离线测试门禁 | 默认测试设计为确定性和离线 |
| 文档治理 | Active 文档有 frontmatter、索引和完整性检查 |
| Secret 边界 | 真实 secret 只在被忽略的 `secrets/` 中；示例放在 `templates/` 下 |

## ⚠️ Alpha 边界

| 领域 | 仍处于 Alpha 的原因 |
|------|---------------------|
| 公开安装体验 | 项目可从源码使用，但发布产物和包发布尚未自动化 |
| Provider 合同 | Provider/debug 层在成为稳定公开 API 前需要更多合同测试 |
| App delivery schema | `schema_version: 2` 是正式路径，但机器可读 schema 和迁移说明仍在扩展中 |
| Live gate | WSL、SSH、Docker、DNS 和 provider 检查需要明确准备的环境 |

## 🗺️ 近期里程碑

| 里程碑 | 目标 | 退出标准 | 进度 |
|--------|------|----------|------|
| M1: 公开贡献者循环 | 让外部 PR 可自验证 | CI 在 PR 和 push 时运行，issue 模板存在，release check 已文档化 | **部分完成** — CI workflow (`ci.yml`) 覆盖 3-OS 矩阵 fast-gate + release-gate；issue/PR 模板已存在 |
| M2: 发布工程 | 让 tag 可复现 | `uv build` 在 release check 中通过，release notes 被维护 | **部分完成** — `repo release-check` CLI 已存在；`uv build` 和 release notes 自动化待定 |
| M3: 合同硬化 | 让 app delivery 合同可机器检查 | 当前合同的 JSON Schema 存在，CLI 错误携带稳定错误码 | 待定 |
| M4: 运行时拆分 | 降低高风险文件 | App delivery 运行时职责按合同、渲染、部署、验证和 inventory/doc sync 拆分 | 待定 |
| M5: Provider 合同 | 将 provider 细节保持在正式 surface 之后 | Provider 行为有聚焦的合同测试，公开文档指向 task-entry | 待定 |

## 📌 长期阶段

| 阶段 | 目标 | 追踪 |
|------|------|------|
| P0: 蓝图落库 | 将 active 战略蓝图和工作计划机制入库 | [Workbook](docs/maintainers/agentplane-roadmap-workbook.md#p0-蓝图落库与任务机制建立) |
| P1: 继续执行协议 | 让"继续执行"能可靠恢复当前阶段、下一任务和状态更新 | [Workbook](docs/maintainers/agentplane-roadmap-workbook.md#p1-任务书与继续执行闭环稳定) |
| P2: 证据模型 | 定义 Operation Receipt、Exception Review | [蓝图](docs/reference/agentplane-ultimate-blueprint.md#长期机制) |
| P3: 项目模型 | 区分 Project Registry、App Catalog 和 Blueprint | [蓝图](docs/reference/agentplane-ultimate-blueprint.md#长期机制) |
| P4: 生命周期示范 | 证明低风险 app 从接入到退役的完整生命周期 | [Workbook](docs/maintainers/agentplane-roadmap-workbook.md#p4-应用生命周期示范闭环) |
| P5: 可视化增强 | 扩展 repo status 或静态面板，增加阶段、任务、项目和风险视图 | [Workbook](docs/maintainers/agentplane-roadmap-workbook.md#p5-可视化控制面增强) |
| P6: 受控扩展 | 增加安全、并发、审批和多 Agent 边界 | [Workbook](docs/maintainers/agentplane-roadmap-workbook.md#p6-安全并发与多-agent-受控扩展) |
| P7: 生命周期验证 | 用真实 app 跑通 onboard → verify → receipt → offboard 完整链路 | **已完成** — [Workbook](docs/maintainers/agentplane-roadmap-workbook.md#p7-应用生命周期真实验证) |

## 🚫 非目标

- AgentPlane 不是 Terraform 或完整 GitOps 控制器的替代品
- AgentPlane 不是 SSH 脚本集合
- AgentPlane 不在公开 Git 中存储生产 secret、私有主机台账或维护者本地 runbook
- AgentPlane 不让应用仓库持有生产控制面状态
