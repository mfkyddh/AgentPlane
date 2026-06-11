---
status: active
owner: AgentPlane maintainers
last_verified: 2026-06-11
superseded_by: null
audience: both
---

# 静态站点（Ingress）全生命周期验证 Runbook

> 记录静态站点在 prod0-main 环境下的完整验证过程，形成可复制的模板。

---

## 概述

**目标应用**: 静态站点（通过 Ingress/Website 管理）

**验证环境**: prod0-main

**验证目标**: 证明静态站点可通过 AgentPlane 完成完整的 Plan → Apply → Verify → Record 闭环。

**应用特点**:
- 静态 HTML/CSS/JS 文件
- 通过 OpenResty/Nginx 托管
- 需要域名和 SSL 证书
- 通过 Ingress 对象管理

---

## 前置条件

- [ ] prod0-main 可通过 SSH 访问
- [ ] OpenResty 已安装并运行
- [ ] AgentPlane CLI 已安装
- [ ] 域名已解析到 prod0-main
- [ ] SSL 证书已配置（可选）

---

## 验证步骤

### 1. Ingress 搜索

```bash
agentplane ingress search --target prod0-main --repo-root .
```

**验证点**:
- [ ] 返回 JSON 格式结果
- [ ] 包含 `command: "ingress"`
- [ ] 包含 `action: "search"`
- [ ] 返回已配置的 ingress 列表

### 2. Ingress 详情获取

```bash
agentplane ingress get --target prod0-main --alias <alias> --repo-root .
```

**验证点**:
- [ ] 返回 ingress 定义
- [ ] 包含域名信息
- [ ] 包含代理配置
- [ ] 包含 live 状态

### 3. Ingress 健康验证

```bash
agentplane ingress verify --target prod0-main --alias <alias> --repo-root .
```

**验证点**:
- [ ] 返回 `ok: true` 或详细状态
- [ ] 包含 DNS 解析检查
- [ ] 包含 SSL 证书检查（如配置）
- [ ] 包含 HTTP 响应检查

### 4. Ingress 发布计划

```bash
agentplane ingress publish plan --target prod0-main --alias <alias> --domain <domain> --proxy http://localhost:<port> --repo-root .
```

**验证点**:
- [ ] 返回发布计划
- [ ] 包含域名配置
- [ ] 包含代理配置
- [ ] 不实际执行发布

### 5. Ingress 发布执行

```bash
agentplane ingress publish apply --target prod0-main --alias <alias> --domain <domain> --proxy http://localhost:<port> --repo-root . --execute
```

**验证点**:
- [ ] 创建网站配置
- [ ] 配置 SSL 证书（如需要）
- [ ] 重启 OpenResty

### 6. Ingress 发布验证

```bash
agentplane ingress publish verify --target prod0-main --alias <alias> --repo-root .
```

**验证点**:
- [ ] 网站可访问
- [ ] SSL 证书有效
- [ ] HTTP 响应正常

### 7. Inventory 刷新

```bash
agentplane ingress refresh-ledger --target prod0-main --repo-root . --write
```

**验证点**:
- [ ] 返回 `target: "prod0-main"`
- [ ] 包含 ingress 条目
- [ ] 写入 inventory 文件

### 8. Ledger 验证

```bash
cat inventory/servers/prod0-main/ledgers/ingress.json
```

**验证点**:
- [ ] 文件存在且为有效 JSON
- [ ] 包含已发布的 ingress 条目
- [ ] 包含状态信息

---

## 验证结果模板

```markdown
## 验证日期: YYYY-MM-DD

### 静态站点 (<alias>)
- Ingress 搜索: ✓/✗
- 详情获取: ✓/✗
- 健康验证: ✓/✗
- 发布计划: ✓/✗
- 发布执行: ✓/✗
- 发布验证: ✓/✗
- Inventory 刷新: ✓/✗
- Ledger 验证: ✓/✗

### 总体结果
- 验证通过: ✓/✗
- 发现问题: [列出]
- 改进建议: [列出]
```

---

## 常见问题

### 域名无法解析
- 检查 DNS 配置
- 确认域名已正确解析到 prod0-main IP
- 使用 `nslookup <domain>` 验证

### SSL 证书问题
- 检查证书是否过期
- 确认证书链完整
- 使用 `openssl s_client -connect <domain>:443` 验证

### 网站不可访问
- 检查 OpenResty 状态: `systemctl status openresty`
- 查看 OpenResty 日志: `tail -f /var/log/openresty/error.log`
- 检查端口绑定: `netstat -tlnp | grep 80`

### 配置文件问题
- 检查 ingress 定义文件
- 确认代理目标地址正确
- 验证 OpenResty 配置语法: `openresty -t`

---

## 关联文档

- [sub2api 双环境验证 Runbook](sub2api-dual-env-verification.md)
- [基础设施服务验证 Runbook](infrastructure-services-verification.md)
- [CLIProxyAPI 验证 Runbook](cliproxyapi-verification.md)
- [架构](../core/architecture.md)
- [命令参考](../command-reference.md)
