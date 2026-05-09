---
status: active
owner: AgentPlane maintainers
last_verified: 2026-05-09
date: 2026-05-09
---

# 009. 合并 3 个重叠数据类为 1 个 CommandSpec

## 背景

执行链路中存在 3 个高度重叠的数据类：

- `ExecutionPlan`：命令计划（backend_type、argv、env_refs、input_refs 等）
- `ExecutionBindings`：运行时绑定（cwd_values、env_values、input_values）
- `PlannedExecutionStep`：包装 ExecutionPlan + ExecutionBindings

这 3 个类传递高度重叠的信息，每次执行都需要同时传递 plan 和 bindings，维护成本高。

## 决策

合并为 1 个 `CommandSpec` 数据类：

```python
@dataclass(frozen=True)
class CommandSpec:
    backend_type: BackendType
    argv: tuple[str, ...]
    cwd: Path | str | None = None
    env: Mapping[str, str] = field(default_factory=dict)
    stdin_text: str | None = None
    timeout: int = 120
    expected_outputs: tuple[str, ...] = ()
    capabilities: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)
```

- `CommandStep` 包装 `CommandSpec`（替代 `PlannedExecutionStep`）
- 旧类保留但不再在新代码中使用
- `to_payload()` 过滤非序列化 metadata 值

## 理由

- 1 个类比 3 个更易理解
- 消除 ref-based 间接层（cwd_ref → resolve_cwd → cwd 值）
- 新人/AI 能在 10 分钟内理解完整执行链路
- `to_payload()` 保持向后兼容（13 个文件使用）

## 替代方案

| 方案 | 为什么放弃 |
|------|-----------|
| 保持 3 个类 + 打补丁 | 复杂度随功能增长继续膨胀 |
| 用 dict 替代 dataclass | 失去类型安全和 IDE 支持 |
| 引入 Protocol/ABC | 过度设计；当前只有 1 种实现 |

## 影响

- 14 个文件从旧 API 迁移到新 API
- 后端 runner 新增 `render_spec()`/`execute_spec()` 方法
- 旧 `render()`/`execute()` 方法保留向后兼容

## 相关决策

- [006](006-ssh-pooling.md) — SSH 连接池化

## 关联文档

- [架构](../core/architecture.md) — 跨平台执行模型
