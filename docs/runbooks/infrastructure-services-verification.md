---
status: active
owner: AgentPlane maintainers
last_verified: 2026-06-11
superseded_by: null
audience: both
---

# 基础设施服务全生命周期验证 Runbook

> 记录 PostgreSQL 和 Redis 在 prod0-main 环境下的完整验证过程，形成可复制的模板。

---

## 概述

**验证服务**:
- PostgreSQL 18（postgres18-prod）
- Redis 7（redis7-prod）

**验证环境**: prod0-main

**验证目标**: 证明基础设施服务可通过 AgentPlane 完成完整的 Plan → Apply → Verify → Record 闭环。

---

## 前置条件

- [ ] prod0-main 可通过 SSH 访问
- [ ] Docker 已安装并运行
- [ ] AgentPlane CLI 已安装
- [ ] secrets/services/ 下有对应的 env 文件

---

## 验证步骤

### 1. 服务状态检查

**检查 PostgreSQL**:
```bash
agentplane service search --target prod0-main --name postgres
```

**验证点**:
- [ ] 返回 JSON 格式结果
- [ ] 包含 `command: "service"`
- [ ] 包含 `action: "search"`
- [ ] postgres18-prod 在结果列表中

**检查 Redis**:
```bash
agentplane service search --target prod0-main --name redis
```

**验证点**:
- [ ] redis7-prod 在结果列表中

### 2. 服务详情获取

**PostgreSQL 详情**:
```bash
agentplane service get --target prod0-main --name postgres18-prod
```

**验证点**:
- [ ] 返回容器状态（running/stopped）
- [ ] 包含镜像版本信息
- [ ] 包含端口绑定信息

**Redis 详情**:
```bash
agentplane service get --target prod0-main --name redis7-prod
```

### 3. 服务健康验证

**PostgreSQL 健康检查**:
```bash
agentplane service verify --target prod0-main --name postgres18-prod
```

**验证点**:
- [ ] 返回 `ok: true` 或详细的健康状态
- [ ] 包含连接测试结果
- [ ] 包含版本信息

**Redis 健康检查**:
```bash
agentplane service verify --target prod0-main --name redis7-prod
```

### 4. 服务计划操作

**PostgreSQL 重启计划**:
```bash
agentplane service plan --target prod0-main --name postgres18-prod --operation restart
```

**验证点**:
- [ ] 返回操作计划
- [ ] 包含预估影响
- [ ] 不实际执行操作

### 5. Inventory 刷新

**刷新服务台账**:
```bash
agentplane service refresh-ledger --target prod0-main --repo-root . --write
```

**验证点**:
- [ ] 返回 `target: "prod0-main"`
- [ ] 包含服务数量统计
- [ ] 写入 inventory 文件

### 6. Ledger 验证

**检查 Ledger 文件**:
```bash
cat inventory/servers/prod0-main/ledgers/services.json
```

**验证点**:
- [ ] 文件存在且为有效 JSON
- [ ] 包含 postgres18-prod 条目
- [ ] 包含 redis7-prod 条目
- [ ] 包含状态信息

---

## 验证结果模板

```markdown
## 验证日期: YYYY-MM-DD

### PostgreSQL (postgres18-prod)
- 状态检查: ✓/✗
- 详情获取: ✓/✗
- 健康验证: ✓/✗
- 计划操作: ✓/✗
- Inventory 刷新: ✓/✗

### Redis (redis7-prod)
- 状态检查: ✓/✗
- 详情获取: ✓/✗
- 健康验证: ✓/✗
- 计划操作: ✓/✗
- Inventory 刷新: ✓/✗

### 总体结果
- 验证通过: ✓/✗
- 发现问题: [列出]
- 改进建议: [列出]
```

---

## 常见问题

### PostgreSQL 连接失败
- 检查 `secrets/services/postgres/admin.prod0.env` 是否存在
- 确认容器是否运行: `docker ps | grep postgres`
- 检查端口是否开放: `netstat -tlnp | grep 5432`

### Redis 连接失败
- 检查 `secrets/services/redis/admin.prod0.env` 是否存在
- 确认容器是否运行: `docker ps | grep redis`
- 检查 Redis 配置: `infra/compose/redis/redis.conf`

---

## 关联文档

- [sub2api 双环境验证 Runbook](sub2api-dual-env-verification.md)
- [架构](../core/architecture.md)
- [命令参考](../command-reference.md)
