---
status: active
owner: AgentPlane maintainers
last_verified: 2026-04-25
superseded_by: null
audience: human

---

# 🚀 部署你的第一个应用

结论：跟着本教程，你会把 `sub2api` 样例应用部署到 WSL 开发环境，走完"接入 → 校验 → 构建 → 部署 → 验证"完整闭环。

## 前置条件

- Windows + WSL2 已安装
- AgentPlane 仓库已 clone 到本地
- Docker 在 WSL 中可用
- 你有 sub2api 应用仓库的访问权限

## 第一步：让 AgentPlane 认识你的应用

当前应用列表是空的，需要先把应用登记进来：

```bash
agentplane app delivery onboard --target wsl --app sub2api --repo-root .
```

**预期输出**：

```text
[INFO] Onboarding sub2api -> wsl
[INFO] App entry created: inventory/apps/catalog.json
[INFO] Config path: deploy/agentplane/contract.yaml
[INFO] Next: validate-contract
```

> 💡 如果失败，检查应用仓库的 `deploy/agentplane/contract.yaml` 是否存在，以及 `sub2api` 仓库根是否可访问。

## 第二步：校验交付合同

约定书是 AgentPlane 和你之间的协议，规定了怎么构建、怎么运行、怎么验证：

```bash
agentplane app delivery validate-contract --target wsl --app sub2api --repo-root .
```

**预期输出**：

```text
[PASS] schema_version: 2
[PASS] artifact.build_command exists
[PASS] packaging.package_command exists
[PASS] runtime.ports declared
[PASS] infra.tenant_resources valid
```

> 💡 如果失败，看 [App Delivery 失败处理](../runbooks/app-delivery-failure-handling.md) 的"约定书或资源配置失败"部分。

> 💡 如果失败，看 [App Delivery 失败处理](../runbooks/app-delivery-failure-handling.md) 的"合同或 app resource 失败"部分。

## 第三步：构建运行时产物

```bash
agentplane app delivery build-artifact --target wsl --app sub2api --repo-root . --image-tag latest --dry-run
```

先 `--dry-run` 预览构建命令，确认无误后再执行：

```bash
agentplane app delivery build-artifact --target wsl --app sub2api --repo-root . --image-tag latest --execute
```

**预期输出**：

```text
[INFO] Building artifact for sub2api @ wsl
[INFO] Output: dist/oplinux/
[INFO] Build completed, tag: latest
```

## 第四步：打包镜像

```bash
agentplane app delivery package-runtime --target wsl --app sub2api --repo-root . --image-tag latest --execute
```

**预期输出**：

```text
[INFO] Packaging runtime image: sub2api:latest
[INFO] Image built locally
```

## 第五步：部署到 WSL

先预览部署计划：

```bash
agentplane app delivery deploy --target wsl --app sub2api --repo-root . --image-ref sub2api:latest --dry-run
```

确认计划中的容器名、端口映射、挂载卷都正确后，执行部署：

```bash
agentplane app delivery deploy --target wsl --app sub2api --repo-root . --image-ref sub2api:latest --execute
```

**预期输出**：

```text
[INFO] Deploying sub2api to wsl
[INFO] Compose up: sub2api
[INFO] Container started: sub2api
```

> 💡 如果 deploy 失败，先不要重试！记录错误输出，然后看 [App Delivery 失败处理](../runbooks/app-delivery-failure-handling.md)。

## 第六步：验证部署

```bash
agentplane app delivery verify --target wsl --app sub2api --repo-root . --execute
```

**预期输出**：

```text
[PASS] Container running: sub2api
[PASS] Health probe: http://127.0.0.1:18080/health -> {"status":"ok"}
[PASS] All checks passed
```

## 第七步：查看应用状态

```bash
agentplane infra inventory wsl --repo-root .
```

**预期输出**：

```text
Target: wsl
  App: sub2api
    Status: running
    Image: sub2api:latest
    Ports: 18080:8080
    Health: ok
```

## 你现在做到了什么

| 步骤 | 成果 |
|------|------|
| Onboard | AgentPlane 认识了 `sub2api` |
| Validate | 合同校验通过，构建/部署条件已满足 |
| Build | 生成了运行时产物 |
| Deploy | 应用在 WSL 中运行起来 |
| Verify | 健康检查通过，服务可用 |

## 下一步

- **部署到生产**：把 `--target wsl` 换成 `--target prod0-main`，先 `--dry-run` 再 `--execute`
- **排查失败**：看 [排查部署失败](./troubleshoot-failed-deployment.md)
- **查看运行状态**：运行 `agentplane infra inventory wsl --repo-root .`

## 常用命令速查

```bash
# 查看应用日志
agentplane infra remote bash wsl --repo-root . -- docker logs sub2api

# 停止应用
agentplane infra remote bash wsl --repo-root . -- docker compose -f /opt/agentplane/apps/sub2api/compose.yaml down

# 重新验证
agentplane app delivery verify --target wsl --app sub2api --repo-root . --execute
```
