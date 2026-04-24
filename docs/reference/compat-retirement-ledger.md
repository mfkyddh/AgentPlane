---
status: active
owner: AgentPlane maintainers
last_verified: 2026-04-02
superseded_by: null
---

# 兼容入口退役台账

本文用于记录 compat 入口什么时候还能用、替代入口是什么、何时允许删除。compat 入口不是默认入口，正式优先级固定为：

`agentplane.cli > compat script > runbook > ad-hoc shell`

## 台账字段

| 字段 | 含义 |
| --- | --- |
| `compat_entry` | 当前 compat 入口路径或命令 |
| `replacement` | 正式替代入口 |
| `allowed_callers` | 仍允许使用它的脚本、文档或自动化 |
| `last_verified` | 最近一次确认仍可工作的日期 |
| `remove_when` | 何时可以删除 |
| `removal_test` | 删除前必须通过的验证 |

Contract:

- 每行必须包含 `compat_entry`、`replacement`、`allowed_callers`、`last_verified`、`remove_when`、`removal_test` 六列，且不得留空。
- 只要 `compat_entry` 仍在本台账中，对应 repo 路径就必须仍然存在。
- `replacement` 必须是 formal CLI，前缀固定为 `uv run python -m agentplane.cli`；如有多个正式替代入口，固定使用 ` / ` 分隔。
- `last_verified` 必须使用 `YYYY-MM-DD`。
- `allowed_callers` 只表示例外调用方，不表示默认入口资格。

## 当前台账

| compat_entry | replacement | allowed_callers | last_verified | remove_when | removal_test |
| --- | --- | --- | --- | --- | --- |
| `agentplane/scripts/remote/run_remote_bash.sh` | `uv run python -m agentplane.cli infra remote bash ...` | 历史 runbook、人工救援 | `2026-04-24` | active docs 与自动化不再默认引用时 | 远端 dry-run 与最小远端脚本验证通过 |
| `agentplane/scripts/onepanel/api_request.py` | `uv run python -m agentplane.cli onepanel ...` | provider/debug 低层场景 | `2026-04-24` | 无 active docs 把它当默认入口时 | CLI 帮助、runbook、技能测试通过 |
