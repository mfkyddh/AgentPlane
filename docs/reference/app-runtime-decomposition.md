---
status: active
owner: AgentPlane maintainers
last_verified: 2026-04-24
superseded_by: null
audience: agent

---

# App Runtime 拆分路线

结论：App runtime 与测试 helper 的拆分路线，避免单体 helper 持续膨胀。

本文定义 `agentplane/domain/app/runtime.py` 和 `tests/support/app_delivery.py` 的减重路线。目标是降低 AI Agent 修改核心交付链路时的误伤概率。

## 当前问题

| 文件 | 问题 | 处理方向 |
| --- | --- | --- |
| `agentplane/domain/app/runtime.py` | 聚合了合同解析、版本推荐、构建、装箱、发货、渲染、部署、验证、回滚、inventory、doc-sync | 按交付阶段拆到窄模块 |
| `tests/support/app_delivery.py` | 同时提供 CLI helper、contract fixture、target fixture、secret fixture、compose fixture、fake command helper | 按 fixture 职责拆到 helper 模块 |

## 目标模块边界

| 目标模块 | 职责 |
| --- | --- |
| `agentplane/domain/app/versioning.py` | 推荐版本、tag、delivery version、git sha 读取 |
| `agentplane/domain/app/contracts.py` | 合同加载、规范化、schema 检查 |
| `agentplane/domain/app/rendering.py` | runtime compose、env、artifact 渲染 |
| `agentplane/domain/app/deployment.py` | deploy、rollback、remote step 构建 |
| `agentplane/domain/app/verification.py` | 部署后验证 payload 和健康探测 |
| `agentplane/domain/app/inventory_sync.py` | inventory-refresh 和 doc-sync 数据汇总 |
| `tests/support/app_delivery_cli.py` | 测试 CLI 调用 |
| `tests/support/app_delivery_contracts.py` | 合同 fixture 与 catalog fixture |
| `tests/support/app_delivery_targets.py` | target-specific inventory、compose、secret fixture |

## 执行规则

- 不新增 `runtime.py` 的职责；新行为必须进入目标模块。
- 修改现有行为时，先补聚焦测试，再移动一个职责块。
- 每次拆分提交只移动一个职责，不混入功能改动。
- 拆分完成后删除旧 facade 中的对应函数，避免双入口长期存在。
- 测试 helper 禁止继续使用新的 `from tests.support.app_delivery import *`；新增测试必须显式导入所需 helper。
