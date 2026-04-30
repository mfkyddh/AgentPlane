---
status: active
owner: AgentPlane maintainers
last_verified: 2026-04-29
superseded_by: null
audience: agent
layer: engineering
---

# AgentPlane 锁规则与审批边界

结论：本文档定义 AgentPlane 的文件级锁规则和审批门禁概念模型。首轮只定义规则，不实现运行时代码。锁机制和审批 CLI 扩展推到后续阶段。

## 文件级锁规则

### 锁粒度

| 粒度 | 锁什么 | 适用场景 | P6 决策 |
| --- | --- | --- | --- |
| 仓库级 | 整个 repo | 简单但粗暴 | ❌ 不采用 |
| 文件级 | `inventory/` 和 `ledger` 下的写操作文件 | 当前最合理 | ✅ 首轮定义规则 |
| 对象级 | 同一 target 的同一 app | 远期需求 | ❌ 推后 |

### 锁规则表

| 属性 | 规则 | 说明 |
| --- | --- | --- |
| 锁粒度 | 文件级 | 只锁 `inventory/` 和 `ledger` 下的写操作文件 |
| 锁范围 | 不锁文档、不锁代码 | `docs/`、`agents/`、`skills/` 等不锁 |
| 锁获取 | 写操作前必须获取锁 | 获取失败则排队或拒绝 |
| 锁释放 | 操作完成或异常退出后必须释放 | 包括正常返回和异常路径 |
| 锁超时 | 建议 30 秒 | 防止死锁，后续阶段可配置 |
| 锁文件命名 | `<target-file>.lock` | 与 targets 文件同目录 |

### 锁获取/释放伪代码

```
function acquire_lock(file_path):
    lock_file = file_path + ".lock"
    try:
        fd = open(lock_file, O_CREAT | O_EXCL)
        write(fd, "agent_id=<id>\ntimestamp=<iso8601>\n")
        close(fd)
        return fd
    except FileExistsError:
        # 锁已存在，检查是否超时
        if lock_age(lock_file) > 30s:
            break_lock(lock_file)
            retry
        else:
            raise LockAcquisitionFailed()

function release_lock(fd, lock_file):
    close(fd)
    unlink(lock_file)
```

### 跨平台兼容性

| 平台 | 推荐方案 | 说明 |
| --- | --- | --- |
| Linux / WSL | `fcntl.flock()` | POSIX 标准，内核级锁 |
| Windows | `msvcrt.locking()` 或 `filelock` 库 | `filelock` 库跨平台，纯 Python |
| 跨平台统一 | `filelock` 库 | 首轮推荐，后续阶段实现时评估 |

**P6 决策**：首轮只定义规则，不引入 `filelock` 依赖。后续阶段实现时再评估库选择。

## 审批门禁

### 审批门禁 vs 阶段门

这是两个不同层面的机制，不得混为一谈：

| 机制 | 层面 | 触发时机 | 已有基础 | P6 定义内容 |
| --- | --- | --- | --- | --- |
| 阶段门 | 长期推进决策 | 阶段开始前 | workbook 阶段门表 | 已有，不在本文档重复 |
| 审批门禁 | 单次高风险操作 | 执行前 | `--dry-run` / `--execute` | 概念模型 + 未来 CLI 扩展方案 |

### 高风险操作分类

| 风险等级 | 操作类型 | 示例命令 | 审批要求 |
| --- | --- | --- | --- |
| `high` | 生产部署、回滚、fixture apply | `app delivery deploy --execute` | 必须 `--approve` |
| `medium` | staging 部署、ledger 强制刷新 | `app delivery deploy --target staging --execute` | 建议 `--approve` |
| `low` | dry-run、verify、只读查询 | `app delivery verify --dry-run` | 无需审批 |

### 未来 CLI 扩展方案

建议未来在 CLI 中扩展审批模型：

| 命令形态 | 含义 | 当前基础 |
| --- | --- | --- |
| `--dry-run` | 只看计划，不执行 | 已有 |
| `--execute` | 执行低风险操作 | 已有 |
| `--execute --approve` | 执行高风险操作，需显式审批 | P6 定义概念，后续实现 |

审批流程（后续阶段实现）：

```
1. Agent 检测到高风险操作
2. 检查 --approve flag
   - 有：继续执行
   - 无：提示需要 --approve，暂停
3. 人类显式传入 --approve
4. 执行操作
5. 生成 Operation Receipt（含 agent_id）
```

### 审批记录

每次审批（无论通过或拒绝）都应生成 Operation Receipt 或 Exception Review：

| 场景 | 必须产物 | 模板位置 |
| --- | --- | --- |
| 审批通过并执行 | Operation Receipt | [workbook P2](../maintainers/agentplane-roadmap-workbook.md#operation-receipt-模板) |
| 审批拒绝 | Exception Review | [workbook P2](../maintainers/agentplane-roadmap-workbook.md#exception-review-模板) |
| 审批超时 | Exception Review | 同上 |

## Agent ID 传递

### 目的

为支持状态漂移检测（T3 威胁）和操作审计，需要在 Operation Receipt 中增加 `agent_id` 字段。

### Agent ID 概念模型

| 概念 | 含义 | 示例 |
| --- | --- | --- |
| `agent_id` | Agent 的唯一标识 | `main`、`sub-P6-T2`、`human` |
| `parent_agent_id` | 派遣者 ID（子 Agent 专用） | `main`（子 Agent 由 main 派遣） |
| `operation_id` | 每次正式操作的唯一 ID | `P6-T2-2026-04-29-001` |

### Operation Receipt 扩展（未来）

当前 P2 定义的 Operation Receipt 模板不含 `agent_id`。未来扩展时增加：

```markdown
#### Operation Receipt

| 字段 | 内容 |
| --- | --- |
| 任务 | <阶段任务 ID 和标题> |
| Agent ID | <执行本次操作的 Agent 标识> |
| 父 Agent ID | <派遣者 ID，主 Agent 留空> |
| 目标 | <本次任务要达成什么> |
| 触发 Skill | <使用或匹配到的 Skill；无则写"无，原因：..."> |
| 正式命令或动作 | <关键 agentplane 命令、验证命令或文档动作摘要> |
| 验证结果 | <通过/失败/未运行及原因> |
| 证据链接 | <相关文档、commit、ledger、status 输出或报告引用> |
| 后续影响 | <推进到哪个阶段、留下什么 follow-up> |
```

### 实现路径

| 阶段 | 内容 |
| --- | --- |
| P6（当前） | 定义概念和扩展方案，不修改 P2 模板 |
| 后续阶段 | 修改 P2 Operation Receipt 模板，增加 `agent_id` / `parent_agent_id` 字段 |
| 后续阶段 | CLI 高风险命令执行时自动注入 `agent_id` |
| 远期 | `repo status` 展示近期操作归属（基于 Receipt 或 ledger） |

## 与威胁模型的关系

本文档定义的规则，直接缓解威胁模型中的两类威胁：

| 威胁 | 缓解措施 | 所在章节 |
| --- | --- | --- |
| T1 意外破坏 | 文件级锁规则 | 锁规则章节 |
| T2 越权操作 | 审批门禁概念模型 + 高风险操作分类 | 审批门禁章节 |
| T3 状态漂移 | Agent ID 传递 + Operation Receipt 扩展 | Agent ID 传递章节 |

## 相关文档

- [威胁模型](threat-model.md)
- [子 Agent 协作边界](agent-collaboration.md)
- [阶段工作计划](../maintainers/agentplane-roadmap-workbook.md)
- [Operation Receipt 模板](../maintainers/agentplane-roadmap-workbook.md#operation-receipt-模板)

## 后续计划

| 计划 | 内容 | 阶段 |
| --- | --- | --- |
| 规则定义 | 本文档已完成锁规则、审批门禁、Agent ID 的概念定义 | P6 |
| 文件锁实现 | 选择跨平台锁库（`filelock` 或 stdlib），在写操作前加锁 | 后续阶段 |
| 审批 CLI 扩展 | `--execute --approve` 实现，高风险操作强制检查 | 后续阶段 |
| Operation Receipt 扩展 | 修改 P2 模板，增加 `agent_id` 字段 | 后续阶段 |
| 威胁检测增强 | `repo status` 展示近期操作归属 | 远期 |
