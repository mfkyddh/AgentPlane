---
status: active
owner: AgentPlane maintainers
last_verified: 2026-04-24
superseded_by: null
---

# 代码风格规范

本文定义 AgentPlane 仓库的代码风格基线。目标不是追求漂亮，而是让多人、人机协作和长期维护时少猜、少争、少踩坑。

## 基本原则

| 规则 | 要求 |
| --- | --- |
| 自动优先 | 能交给工具检查的风格，不靠人工 review 记忆 |
| 小步改动 | 风格调整不混入行为变更；大范围格式化必须单独提交 |
| 明确失败 | 生产代码不要用宽泛兜底、假数据或后处理补丁掩盖问题 |
| 就近一致 | 新代码优先贴近所在模块的既有结构和命名 |
| 可读优先 | 抽象只在减少真实复杂度时引入，不为了“看起来高级”拆层 |

## Python 风格

- Python 目标版本固定为 `3.12+`。
- lint 使用 `ruff` 管理，当前覆盖导入排序、未使用导入和明显运行错误。
- 测试禁止使用星号导入；新增测试必须显式导入所需 helper。
- 行宽基线为 `120`，用于减少无意义换行；长命令、长路径、长错误消息仍应主动拆分。
- 公共函数、跨模块函数和复杂返回值应写类型标注。
- 领域模型优先使用 `dataclass`、清晰的 `dict` contract 或现有模型，不新增隐式字符串协议。
- 异常要暴露可定位原因；不要用裸 `except`，宽泛 `except Exception` 必须解释边界或只出现在 CLI 顶层。
- 文件读写默认显式 `encoding="utf-8"`。

## CLI 与运行时代码

- 正式能力必须挂到 `agentplane ...` 入口，不把 `scripts/` 变成第二控制面。
- 计划、执行、验证要分层：`plan` 不改真实状态，`--execute` 才允许改变现场。
- 涉及 SSH、Docker、WSL、远端 provider 的逻辑要走 runtime/backend/provider 边界，不在业务函数里手写多层 shell。
- 需要展示命令时，区分机器执行的 `argv` 和人类阅读的 `display`。
- 输出 JSON 的命令要保持字段稳定；新增字段优先向后兼容，不随意重命名。

## 测试风格

- 默认测试必须离线、确定性、可在 Windows/macOS/Linux 跑通。
- 真实 WSL、SSH、Docker、provider 验证必须显式打 marker，并通过 live gate 执行。
- 新增共享测试辅助放到 `tests/support/`，不要继续扩大单个大型测试文件。
- 行为变更至少补一个聚焦测试；文档或 contract 变更要补对应的快照或 CLI 合同测试。

## 文档风格

- `AGENTS.md` 只放高信号摘要，详细规则放 `docs/reference/`。
- reference 文档说明长期稳定规则；runbook 说明具体操作步骤。
- 新文档要写清楚适用范围、正式入口、验证方式和退役条件。

## 本地检查

提交前优先运行：

```bash
uv run python -m agentplane.cli repo health-check --repo-root .
```

如果改动只涉及文档，至少确认相关链接和命令示例仍然指向正式入口。
