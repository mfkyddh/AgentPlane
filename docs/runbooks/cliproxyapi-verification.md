---
status: active
owner: AgentPlane maintainers
last_verified: 2026-06-11
superseded_by: null
audience: both
---

# CLIProxyAPI 全生命周期验证 Runbook

> 记录 CLIProxyAPI 在 prod0-main 环境下的完整验证过程，形成可复制的模板。

---

## 概述

**目标应用**: CLIProxyAPI（API 代理服务）

**验证环境**: prod0-main

**验证目标**: 证明业务应用可通过 AgentPlane 完成完整的 Plan → Apply → Verify → Record 闭环。

**应用特点**:
- Go 编写，单二进制部署
- 多端口绑定（API + 回调端口）
- 配置文件驱动
- 需要挂载日志和静态资源

---

## 前置条件

- [ ] prod0-main 可通过 SSH 访问
- [ ] Docker 已安装并运行
- [ ] AgentPlane CLI 已安装
- [ ] secrets/services/cliproxyapi.prod0.env 存在
- [ ] config.yaml 配置文件就绪

---

## 验证步骤

### 1. 应用 Onboard

```bash
agentplane app delivery onboard --target prod0-main --app cliproxyapi --repo-root .
```

**验证点**:
- [ ] catalog.yaml 中存在 cliproxyapi 条目
- [ ] 应用目录结构正确

### 2. Contract 验证

```bash
agentplane app delivery validate-contract --target prod0-main --app cliproxyapi --repo-root .
```

**验证点**:
- [ ] contract.yaml 格式正确
- [ ] 包含所有必需字段（app_id, artifact, packaging, runtime）
- [ ] 镜像名称和标签规则正确

### 3. 服务状态检查

```bash
agentplane service search --target prod0-main --name cliproxyapi
```

**验证点**:
- [ ] 返回 JSON 格式结果
- [ ] cliproxyapi 在结果列表中
- [ ] 状态为 running

### 4. 服务详情获取

```bash
agentplane service get --target prod0-main --name cliproxyapi-prod
```

**验证点**:
- [ ] 返回容器状态
- [ ] 包含镜像版本信息
- [ ] 包含端口绑定信息（8318, 1455, 54545, 51121, 11451）
- [ ] 包含卷挂载信息

### 5. 服务健康验证

```bash
agentplane service verify --target prod0-main --name cliproxyapi-prod
```

**验证点**:
- [ ] 返回健康状态
- [ ] API 端口可访问
- [ ] 回调端口可访问

### 6. 服务计划操作

```bash
agentplane service plan --target prod0-main --name cliproxyapi-prod --operation restart
```

**验证点**:
- [ ] 返回操作计划
- [ ] 包含预估影响
- [ ] 不实际执行操作

### 7. Inventory 刷新

```bash
agentplane service refresh-ledger --target prod0-main --repo-root . --write
```

**验证点**:
- [ ] 返回 `target: "prod0-main"`
- [ ] 包含 cliproxyapi 条目
- [ ] 写入 inventory 文件

### 8. App Ledger 刷新

```bash
agentplane app object refresh-ledger --target prod0-main --repo-root . --write
```

**验证点**:
- [ ] 返回 `target: "prod0-main"`
- [ ] 包含 cliproxyapi 条目
- [ ] 写入 ledger 文件

### 9. Ledger 验证

```bash
cat inventory/servers/prod0-main/ledgers/services.json | grep cliproxyapi
```

**验证点**:
- [ ] 文件存在且为有效 JSON
- [ ] 包含 cliproxyapi 条目
- [ ] 包含状态信息

---

## 验证结果模板

```markdown
## 验证日期: YYYY-MM-DD

### CLIProxyAPI (cliproxyapi-prod)
- Onboard: ✓/✗
- Contract 验证: ✓/✗
- 状态检查: ✓/✗
- 详情获取: ✓/✗
- 健康验证: ✓/✗
- 计划操作: ✓/✗
- Inventory 刷新: ✓/✗
- App Ledger 刷新: ✓/✗

### 总体结果
- 验证通过: ✓/✗
- 发现问题: [列出]
- 改进建议: [列出]
```

---

## 常见问题

### 容器未运行
- 检查 Docker 状态: `docker ps | grep cliproxyapi`
- 查看容器日志: `docker logs cliproxyapi-prod`
- 检查配置文件: `cat config.yaml`

### 端口不可访问
- 检查端口绑定: `netstat -tlnp | grep 8318`
- 检查防火墙规则
- 确认配置文件中的端口设置

### 配置文件问题
- 检查 config.yaml 格式
- 确认 secrets/services/cliproxyapi.prod0.env 存在
- 验证卷挂载路径

---

## 关联文档

- [sub2api 双环境验证 Runbook](sub2api-dual-env-verification.md)
- [基础设施服务验证 Runbook](infrastructure-services-verification.md)
- [架构](../core/architecture.md)
- [命令参考](../command-reference.md)
