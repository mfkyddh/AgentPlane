---
status: active
owner: AgentPlane maintainers
last_verified: 2026-04-29
superseded_by: null
audience: both
layer: technical
---

# 📊 AgentPlane 当前状态与验证

结论：本页教人"怎么看状态"，不是状态本身。先用 `repo status` 查看本地控制面摘要和静态面板，再按需要运行更重的健康检查。

## 查看仓库健康

```bash
agentplane repo status --repo-root .
agentplane repo status --repo-root . --html tmp/agentplane-status.html
agentplane repo health-check --repo-root .
```

`status` 只读本地仓库状态，会聚合文档、隐私边界、Skill、app catalog 和 inventory target 摘要；`--html` 会生成可直接打开的静态面板。`health-check` 会运行仓库默认健康检查，用来确认当前工作区是否适合继续执行。

**预期输出**：

```text
[PASS] Status summary generated
[PASS] 仓库结构检查
[PASS] docs-sanity 链接检查
[PASS] 入口漂移检查
```

## 查看目标环境清单

```bash
# WSL 开发环境
agentplane infra inventory wsl --repo-root .
agentplane infra audit wsl --repo-root .

# 生产环境
agentplane infra inventory prod0-main --repo-root .
agentplane infra audit prod0-main --repo-root .
```

**预期输出**：

```text
Target: wsl
  Network: zqf_network
  Containers: sub2api, ...
  Status: ok / warn / fail
```

## 查看应用运行状态

```bash
agentplane app delivery verify --target wsl --app sub2api --repo-root . --execute
```

**预期输出**：

```text
[PASS] Container running: sub2api
[PASS] Health probe: http://127.0.0.1:18080/health -> {"status":"ok"}
```

## 查看操作记录

```bash
# 最近的操作记录
ls tmp/operation-ledger/

# 最近的验证结果
agentplane repo release-check --repo-root .
```

## 状态解读方法

| 检查结果 | 含义 | 下一步 |
|---------|------|--------|
| `[PASS]` | 一切正常 | 无需操作 |
| `[WARN]` | 有非致命问题 | 查看具体 warning，安排修复 |
| `[FAIL]` | 有致命问题 | 立即排查，参考 [App Delivery 失败处理](./app-delivery-failure-handling.md) |

## 推荐阅读顺序

1. [wsl-host-governance.md](./wsl-host-governance.md)
2. 私有生产机 runbook 保留在本地 ignored 工作区，不进入公开仓库。
3. [app-project-delivery-workflow.md](./app-project-delivery-workflow.md)
4. [onepanel-cli-validation-workflow.md](./onepanel-cli-validation-workflow.md)
