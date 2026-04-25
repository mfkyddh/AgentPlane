---
status: active
owner: AgentPlane maintainers
last_verified: 2026-04-25
superseded_by: null
audience: human

---

# 🔍 排查一次失败的部署

结论：部署失败时，先停在当前阶段，用只读命令定位原因，修约定书后重跑，不要绕过 AgentPlane 手动修现场。

## 场景

你执行了：

```bash
agentplane app delivery deploy --target wsl --app sub2api --repo-root . --image-ref sub2api:latest --execute
```

输出里出现了 `[FAIL]`。现在该怎么办？

## 第一步：不要慌，先记录

把完整的命令和输出复制到本地文本文件。不要急着重试，也不要手动 SSH 进去改东西。

## 第二步：重新运行只读检查

只读检查不会改任何东西，但可以帮你定位问题在哪一层：

```bash
agentplane app delivery validate-contract --target wsl --app sub2api --repo-root .
```

**预期输出（正常时）**：

```text
[PASS] schema_version: 2
[PASS] artifact.build_command exists
[PASS] runtime.ports declared
```

**如果这里也失败了** → 问题在"约定书"层面：
- 应用仓库的 `deploy/agentplane/contract.yaml` 可能被改了
- `inventory/servers/wsl/` 下的配置可能和应用声明不匹配
- 见 [App Delivery 失败处理](../runbooks/app-delivery-failure-handling.md) 的"约定书或资源配置失败"

**如果这里通过了** → 问题在部署执行层面，继续下一步。

## 第三步：检查容器状态

```bash
agentplane infra remote bash wsl --repo-root . -- docker ps -a
```

**预期输出（正常时）**：

```text
CONTAINER ID   IMAGE            STATUS         PORTS
abc123         sub2api:latest   Up 2 minutes   0.0.0.0:18080->8080/tcp
```

**如果容器是 Exited** → 看容器日志：

```bash
agentplane infra remote bash wsl --repo-root . -- docker logs sub2api
```

常见原因：
- 端口冲突（18080 被别的程序占用）
- 环境变量缺失（secrets 文件没配好）
- 应用内部报错（看日志里的 traceback）

## 第四步：回滚到上一个稳定版本

如果 deploy 已经破坏了现场，先回滚：

```bash
# 预览回滚计划
agentplane app delivery rollback --target wsl --app sub2api --repo-root . --dry-run

# 确认计划后执行
agentplane app delivery rollback --target wsl --app sub2api --repo-root . --execute
```

**预期输出**：

```text
[INFO] Rolling back sub2api @ wsl
[INFO] Restoring previous control plane
[INFO] Rollback completed
```

回滚后重新验证：

```bash
agentplane app delivery verify --target wsl --app sub2api --repo-root . --execute
```

## 第五步：修复后重跑

修复了根本原因后，从失败点**之前最近的只读阶段**开始重跑：

```bash
# 1. 重新校验约定书
agentplane app delivery validate-contract --target wsl --app sub2api --repo-root .

# 2. 重新构建（如果构建阶段失败过）
agentplane app delivery build-artifact --target wsl --app sub2api --repo-root . --image-tag latest --execute

# 3. 重新部署
agentplane app delivery deploy --target wsl --app sub2api --repo-root . --image-ref sub2api:latest --execute

# 4. 重新验证
agentplane app delivery verify --target wsl --app sub2api --repo-root . --execute
```

## 常见失败速查

| 错误现象 | 可能原因 | 排查命令 |
|---------|---------|---------|
| `port already in use` | 端口被占用 | `docker ps -a` |
| `no such image` | 镜像没构建或 tag 不对 | `docker images` |
| `exit code 1` | 应用启动失败 | `docker logs <container>` |
| `health probe failed` | 服务起来了但探针不通过 | `curl http://127.0.0.1:18080/health` |
| `registry mismatch` | inventory 和合同声明不一致 | `agentplane infra inventory wsl --repo-root .` |

## 收口碑证

修复完成后，运行仓库级检查确认一切正常：

```bash
agentplane repo health-check --repo-root .
```

**预期输出**：

```text
[PASS] 仓库结构检查
[PASS] docs-sanity 链接检查
[PASS] 入口漂移检查
```

## 核心原则

1. **先只读后写** — 用 `--dry-run` 和只读命令定位问题
2. **修合同不修现场** — 改 `contract.yaml` 或 inventory，让 AgentPlane 重新执行
3. **回滚要快** — deploy 失败后如果现场已被破坏，立即回滚
4. **验证必做** — 每次修复后都要重新 verify
