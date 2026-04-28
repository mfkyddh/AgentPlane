---
status: active
owner: AgentPlane maintainers
last_verified: 2026-04-25
superseded_by: null
audience: human

---

# 🖥️ 把一台新服务器纳入 AgentPlane

结论：跟着本教程，你会把一台全新的 Linux 服务器（示例名为 `prod3-main`）纳入 AgentPlane 管理，完成 SSH 配置、资产清单初始化、基线审计和治理文档创建。

## 前置条件

- 你有新服务器的 root 或 sudo 权限
- 新服务器已安装 Docker 和 Docker Compose
- 你知道新服务器的公网 IP 和 SSH 端口
- AgentPlane 仓库已在你本地配置好

## 第一步：给服务器取个名字

AgentPlane 用"目标名"来识别服务器。现有命名惯例：

| 环境 | 命名格式 | 示例 |
|------|---------|------|
| WSL 开发 | `wsl` | `wsl` |
| 生产机 | `prod<N>-main` | `prod0-main`, `prod1-main` |

假设你的新服务器叫 **`prod3-main`**。

## 第二步：配置 SSH 连接

### 1. 把私钥放到仓库

```bash
# 复制你的 SSH 私钥到仓库
cp ~/.ssh/prod3-main.pem secrets/ssh/keys/
```

### 2. 编辑 SSH 配置

在 `secrets/ssh/config` 中添加新服务器：

```text
Host prod3-main
    HostName 203.0.113.10
    User root
    Port 22
    IdentityFile ~/.ssh/keys/prod3-main.pem
    StrictHostKeyChecking accept-new
```

> 💡 `HostName` 换成你的真实 IP 或域名，`IdentityFile` 指向仓库中的密钥路径。

### 3. 测试 SSH 连接

```bash
agentplane infra remote bash prod3-main --repo-root . -- echo "SSH OK"
```

**预期输出**：

```text
SSH OK
```

> 💡 如果失败，检查 IP、端口、密钥权限（必须 `chmod 600`）和防火墙。

## 第三步：初始化 Secrets

```bash
agentplane bootstrap init-secrets --repo-root .
```

**预期输出**：

```text
[INFO] Created secrets/targets/prod3-main/README.md
[INFO] Created secrets/hosts/prod3-main/ ...
```

这会为新服务器生成 secrets 骨架，但不会写入真实敏感值。

## 第四步：创建资产清单目录

```bash
mkdir -p inventory/servers/prod3-main/ledgers
```

创建初始文件：

```bash
cat > inventory/servers/prod3-main/README.md << 'EOF'
# prod3-main 摘要

## 身份

- 备注：`3号生产机`
- 云厂商：`Example Cloud`
- 公网 IPv4：`203.0.113.10`
- SSH 别名：`prod3-main`

## 资料入口

- 结构化清单：`inventory/servers/prod3-main/inventory.json`
- 本摘要：`inventory/servers/prod3-main/README.md`
EOF
```

## 第五步：生成初始资产清单

```bash
agentplane infra inventory prod3-main --repo-root . --write
```

**预期输出**：

```text
[INFO] Collecting inventory for prod3-main
[INFO] Docker containers: 0
[INFO] Compose services: 0
[INFO] Writing to inventory/servers/prod3-main/inventory.json
```

这会扫描新服务器上的 Docker 容器、服务、网络等信息，并写入资产清单。

## 第六步：运行基线审计

```bash
agentplane infra audit prod3-main --repo-root .
```

**预期输出**：

```text
[INFO] Auditing prod3-main
[PASS] SSH connectivity
[PASS] Docker daemon
[WARN] No managed bridge networks found
[WARN] No compose services found
[INFO] Audit complete. See inventory/servers/prod3-main/ for details.
```

新服务器通常会有一些 warning（没有网络、没有服务），这是正常的。

## 第七步：验证仓库健康

```bash
agentplane repo health-check --repo-root .
```

**预期输出**：

```text
[PASS] 仓库结构检查
[PASS] docs-sanity 链接检查
[PASS] 入口漂移检查
```

## 你现在做到了什么

| 步骤 | 成果 |
|------|------|
| 命名 | 新服务器有了统一标识 `prod3-main` |
| SSH | 可以通过 AgentPlane 远程访问新服务器 |
| Secrets | 新服务器的敏感信息有独立存放位置 |
| 资产清单 | 新服务器的资产信息已登记 |
| 审计 | 基线检查完成，知道当前状态 |

## 下一步

- **部署应用到新服务器**：跟着 [部署你的第一个应用](./deploy-first-app.md)，把 `--target` 换成 `prod3-main`
- **配置网络**：如果新服务器需要与其他服务器通信，先在私有 runbook 中记录目标网络拓扑，再用 `agentplane infra network audit` 验证。
- **创建治理文档**：参考 [control-plane-domain-onboarding.md](../runbooks/control-plane-domain-onboarding.md) 把新服务器纳入正式治理

## 常用命令速查

```bash
# 远程执行命令
agentplane infra remote bash prod3-main --repo-root . -- docker ps

# 重新生成资产清单
agentplane infra inventory prod3-main --repo-root . --write

# 重新审计
agentplane infra audit prod3-main --repo-root .

# 查看新服务器状态
agentplane infra inventory prod3-main --repo-root .
```
