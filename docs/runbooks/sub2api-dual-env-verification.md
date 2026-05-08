---
status: active
owner: AgentPlane maintainers
last_verified: 2026-05-08
audience: both
---

# sub2api 双环境验证 Runbook

> 记录 sub2api 在 WSL 和 prod0-main 双环境下的完整验证过程，形成可复制的模板。

---

## 概述

**目标应用**: sub2api（订阅转 API 服务）

**验证环境**:
- WSL（本地开发/测试）
- prod0-main（生产环境）

**验证时间**: 2026-05-07

**验证结果**: ✓ 成功

---

## 验证步骤

### 1. 应用 Onboard

**WSL 环境**:
```bash
agentplane app delivery onboard --target wsl --app sub2api --repo-root .
```

**prod0-main 环境**:
```bash
agentplane app delivery onboard --target prod0-main --app sub2api --repo-root .
```

**验证点**:
- [ ] catalog.yaml 中存在 sub2api 条目
- [ ] 应用目录结构正确（contract.yaml, docker-compose.yaml 等）

### 2. 构建和部署

**WSL 环境**:
```bash
# 使用 docker compose 直接部署
docker compose up -d
```

**prod0-main 环境**:
```bash
# 使用 candidate precheck + cutover 流程
agentplane app delivery deploy --target prod0-main --app sub2api --repo-root . --dry-run
agentplane app delivery deploy --target prod0-main --app sub2api --repo-root . --execute
```

**验证点**:
- [ ] 容器启动成功
- [ ] 端口映射正确
- [ ] 环境变量注入正确

### 3. 健康检查

**WSL 环境**:
```bash
agentplane service verify --target wsl --name sub2api --repo-root .
```

**prod0-main 环境**:
```bash
agentplane service verify --target prod0-main --name sub2api --repo-root .
```

**验证点**:
- [ ] 容器状态为 running
- [ ] 健康检查通过
- [ ] API 端点可访问

### 4. 证据记录

**操作台账**:
```bash
agentplane app object refresh-ledger --target wsl --repo-root . --write
agentplane app object refresh-ledger --target prod0-main --repo-root . --write
```

**验证点**:
- [ ] operation ledger 中有 deploy 记录
- [ ] 记录包含正确的 op_id、target、result

---

## 发现和修复

### 问题 1: catalog repo_root 路径转换

**现象**: WSL 环境下 catalog 解析失败，提示路径不存在

**原因**: Windows 路径和 WSL 路径格式不一致

**修复**: 在 `agentplane/runtime/wsl_bridge.py` 中添加路径转换逻辑

**验证**: 修复后重新 onboard，catalog 解析成功

### 问题 2: WSL 路径转换

**现象**: 远程执行脚本时路径格式错误

**原因**: SSH 执行时路径未正确转换

**修复**: 使用 `normalize_repo_root_for_current_host()` 函数统一路径格式

**验证**: 修复后远程执行成功

---

## 可复制模板

### 新应用 Onboard 检查清单

1. **准备阶段**:
   - [ ] 确认应用 contract.yaml 完整
   - [ ] 确认 docker-compose.yaml 正确
   - [ ] 确认环境变量模板存在

2. **Onboard 阶段**:
   - [ ] 执行 `app delivery onboard`
   - [ ] 验证 catalog.yaml 更新
   - [ ] 验证目录结构正确

3. **部署阶段**:
   - [ ] 执行 dry-run 验证
   - [ ] 执行实际部署
   - [ ] 验证容器启动

4. **验证阶段**:
   - [ ] 执行 health check
   - [ ] 执行 service verify
   - [ ] 记录 operation ledger

5. **文档化阶段**:
   - [ ] 记录发现的问题和修复
   - [ ] 更新 runbook
   - [ ] 更新 PROGRESS.md

---

## 关联文档

- [架构文档](../core/architecture.md) — 5 域模型和投影模型
- [命令参考](../command-reference.md) — CLI 命令详解
- [入门指南](../getting-started.md) — 5 分钟上手

---

## 变更历史

| 日期 | 变更 | 作者 |
|------|------|------|
| 2026-05-08 | 初始版本，记录 sub2api 双环境验证过程 | AgentPlane |
