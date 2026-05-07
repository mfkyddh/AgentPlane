---
status: archived
owner: AgentPlane maintainers
last_verified: 2026-04-30
superseded_by: null
audience: both
layer: technical
---

# 🛡️ Backup and Recovery

结论：AgentPlane 需要备份的东西分三类——secrets（加密、自动化、R2）、inventory/ledgers（Git 或手动归档）、配置文件（templates 已在 Git，secrets 走自动化）。恢复时先还原 secrets，再同步 inventory，最后验证。

## 🎯 适用场景

| 场景 | 是否适用 |
| --- | --- |
| 日常 secrets 备份验证 | ✅ |
| WSL 环境重建 | ✅ |
| 生产机迁移或重建 | ✅ |
| 误删 secrets 目录后恢复 | ✅ |
| 全站灾难恢复 | ✅ |
| 仅 templates 或 docs 变更 | ❌ 已在 Git，走 Git 恢复即可 |

## 📦 需要备份的内容

| 资产 | 路径 | 敏感度 | 当前备份方式 |
| --- | --- | --- | --- |
| SSH 密钥 | `secrets/ssh/` | 高 | R2 自动加密备份 |
| 服务 secrets | `secrets/services/` | 高 | R2 自动加密备份 |
| 主机级 truth | `secrets/hosts/` | 高 | R2 自动加密备份 |
| 租户配置 | `secrets/tenants/` | 中 | R2 自动加密备份 |
| Env 模板参考 | `templates/` | 无 | Git 跟踪 |
| Inventory 台账 | `inventory/servers/` | 无（但 gitignored） | 手动归档或 Git stash |
| Inventory 摘要 | `inventory/state-snapshot.md` | 无 | 手动归档 |
| App catalog | `inventory/apps/` | 无 | Git 跟踪 |
| Compose 文件 | `infra/compose/` | 无 | Git 跟踪 |
| 生产 compose 覆盖 | `infra/compose/**/docker-compose.prod*.yml` | 低 | 手动归档（gitignored） |
| 操作记录 | `tmp/operation-ledger/` | 无 | 可重建，非关键 |
| Python venv | `.venv/` | 无 | 可重建，非关键 |

## 📋 备份策略

### 频率与保留

| 资产类别 | 备份频率 | 保留份数 | 存储位置 |
| --- | --- | --- | --- |
| secrets（自动化） | 每 5 小时 | 最近 5 份 | Cloudflare R2 `AgentPlane_Backups` 桶 |
| inventory | 变更后手动归档 | 最近 3 份 | 本地离线存储或 R2 |
| Git 仓库 | 每次 push | 按 Git 保留策略 | 远程 Git 托管 |

### Secrets 自动化备份规格

| 参数 | 值 |
| --- | --- |
| 调度器 | WSL 本机 1Panel 计划任务 `wsl-agentplane-secrets-backup` |
| Cron | `0 */5 * * *` |
| 加密方式 | `openssl enc -aes-256-cbc -pbkdf2` |
| 源目录 | `<repo-root>/secrets` |
| 远端桶 | `AgentPlane_Backups` |
| 对象前缀 | `backups/agentplane/secrets-main/` |
| 状态文件 | `/data/agentplane/secrets-backup/state.json` |

详细配置见 `secrets/` 目录下的备份脚本和 `docs/reference/cross-platform.md`。

## 🛠️ 备份操作步骤

### 1. 手动触发 Secrets 备份

正式 CLI 入口：

```bash
env -C <repo-root> agentplane infra automation apply wsl \
  --name wsl-agentplane-secrets-backup \
  --operation run --execute
```

**预期输出**：

```text
status: ok_uploaded
object_key: backups/agentplane/secrets-main/agentplane-secrets-20260430T120000Z-<fingerprint>.tar.gz.enc
deleted_old_backups: 1
```

如果 secrets 内容没有变化，输出为：

```text
status: ok_no_changes
```

### 2. 核验自动化任务是否存在

```bash
env -C <repo-root> agentplane onepanel \
  --env wsl \
  cronjob search \
  --info wsl-agentplane-secrets-backup
```

**预期输出**：返回包含 `wsl-agentplane-secrets-backup` 的 cronjob 列表。

### 3. 导出 Inventory 台账

Inventory 台账是 gitignored 的非敏感状态快照。变更后手动归档：

```bash
# 创建归档时间戳
STAMP=$(date -u +%Y%m%dT%H%M%SZ)

# 打包 inventory 目录
tar -czf /tmp/inventory-backup-${STAMP}.tar.gz \
  -C <repo-root> inventory/servers/ inventory/state-snapshot.md

# 移至长期存储
mv /tmp/inventory-backup-${STAMP}.tar.gz /data/agentplane/backups/
```

### 4. 导出生产 Compose 覆盖文件

生产环境的 compose 覆盖文件也是 gitignored：

```bash
STAMP=$(date -u +%Y%m%dT%H%M%SZ)

tar -czf /tmp/compose-prod-backup-${STAMP}.tar.gz \
  -C <repo-root> \
  $(find infra/compose -name 'docker-compose.prod*.yml' 2>/dev/null)
```

## 🔄 恢复操作步骤

### 前置条件

- 目标机器已安装 `uv` 和 `git`
- 拥有 R2 访问凭证（`secrets/services/secrets-backup.r2.wsl.env`）
- 拥有 secrets 加密密码

### 1. 克隆仓库

```bash
git clone <repo-url> <repo-root>
cd <repo-root>
```

### 2. 恢复 Secrets

#### 方式 A：从 R2 下载最新备份

需要从 R2 下载最新的 `.tar.gz.enc` 文件。使用 `agentplane` CLI 或手动通过 S3 兼容客户端：

```bash
# 查看 R2 上的备份列表（需配置 R2 凭证）
# 从 secrets-backup state 文件中获取 last_uploaded_key
cat /data/agentplane/secrets-backup/state.json
```

使用 openssl 解密并解压：

```bash
# 解密
openssl enc -aes-256-cbc -pbkdf2 -d \
  -in secrets-backup.tar.gz.enc \
  -out secrets-backup.tar.gz \
  -pass env:AGENTPLANE_SECRETS_BACKUP_PASSWORD

# 解压到仓库根目录
tar -xzf secrets-backup.tar.gz -C <repo-root>/

# 清理临时文件
rm -f secrets-backup.tar.gz secrets-backup.tar.gz.enc
```

#### 方式 B：从本地离线备份恢复

如果维护了本地离线备份：

```bash
tar -xzf /data/agentplane/backups/secrets-latest.tar.gz -C <repo-root>/
```

### 3. 恢复 Inventory 台账

```bash
# 从归档恢复
tar -xzf /data/agentplane/backups/inventory-backup-<timestamp>.tar.gz -C <repo-root>/
```

如果 inventory 丢失但 secrets 完整，可通过 CLI 重新生成：

```bash
agentplane infra inventory wsl --repo-root <repo-root>
agentplane infra inventory prod0-main --repo-root <repo-root>
```

### 4. 安装依赖

```bash
cd <repo-root>
uv venv
uv pip install -e .
```

### 5. 验证恢复完整性

```bash
# 验证 secrets 结构
agentplane bootstrap verify-secrets --repo-root <repo-root>

# 验证仓库健康
agentplane repo health-check --repo-root <repo-root>

# 验证 CLI 可用
agentplane --help
```

**预期输出**：

```text
[PASS] SSH config exists
[PASS] SSH keys found: 2
[PASS] Target secrets scaffold: wsl, prod0-main
```

## ✅ 验证备份完整性

### 自动验证（推荐）

每次 secrets 自动备份完成后，脚本会计算内容指纹（SHA-256）并与上次比较。`state.json` 中记录了：

| 字段 | 含义 |
| --- | --- |
| `scan_fingerprint` | 基于文件路径、大小、mtime、mode 的快速指纹 |
| `content_fingerprint` | 基于文件实际内容的强指纹 |
| `last_uploaded_key` | 最近一次上传的 R2 对象 key |
| `last_uploaded_at` | 最近一次上传时间（UTC） |

查看当前备份状态：

```bash
cat /data/agentplane/secrets-backup/state.json
```

### 手动完整性验证

验证本地 secrets 与最新备份一致：

```bash
# 1. 查看 state.json 中的 content_fingerprint
cat /data/agentplane/secrets-backup/state.json | grep content_fingerprint

# 2. 重新计算本地 secrets 指纹
find <repo-root>/secrets -type f | sort | xargs sha256sum | sha256sum

# 3. 运行 bootstrap doctor 全面校验
agentplane bootstrap doctor --repo-root <repo-root>
```

**预期输出**：

```text
[PASS] Repository structure
[PASS] Secrets readiness
[PASS] Backend connectivity
[INFO] AgentPlane is ready for operations
```

### 验证 R2 备份可读

```bash
env -C <repo-root> agentplane infra automation apply wsl \
  --name wsl-agentplane-secrets-backup \
  --operation run --execute
```

返回 `ok_no_changes` 说明本地 secrets 与远端一致，且远端可达。

## ⚠️ 灾难恢复流程

### 场景判断

| 场景 | 恢复策略 |
| --- | --- |
| secrets 目录误删 | 从 R2 最新备份恢复，走"恢复操作步骤"第 2 步 |
| WSL 环境整体丢失 | 重建 WSL → 克隆仓库 → 恢复 secrets → 重新部署应用 |
| 生产机迁移 | 在新机器上恢复 secrets → 运行 inventory → 重新部署 |
| R2 备份不可用 | 从本地离线备份恢复；如无任何备份，需重新走 [Bootstrap Secrets](./bootstrap-secrets.md) |

### 完整灾难恢复流程

1. **评估损失**：确认哪些资产丢失、哪些完好
2. **恢复仓库**：`git clone` 拿到最新代码和 templates
3. **恢复 secrets**：从 R2 或离线备份解密还原
4. **验证 secrets**：`agentplane bootstrap verify-secrets --repo-root <repo-root>`
5. **重建 inventory**：`agentplane infra inventory <target> --repo-root <repo-root>`
6. **验证连通**：`agentplane bootstrap doctor --repo-root <repo-root>`
7. **重新部署应用**：按 [应用交付主流程](./app-project-delivery-workflow.md) 逐个恢复
8. **恢复自动化任务**：

```bash
env -C <repo-root> agentplane infra automation apply wsl \
  --name wsl-agentplane-secrets-backup \
  --operation reconcile --execute --repo-root <repo-root>
```

9. **最终验证**：

```bash
agentplane repo health-check --repo-root <repo-root>
agentplane infra audit wsl --repo-root <repo-root>
agentplane infra audit prod0-main --repo-root <repo-root>
```

### 无任何备份的极端情况

如果 R2 和本地备份均不可用：

1. 按 [Bootstrap Secrets](./bootstrap-secrets.md) 重新生成 secrets 骨架
2. 重新填写 SSH 密钥、服务凭证等所有 secret 值
3. 重新配置 R2 备份自动化（`agentplane infra automation apply wsl --name wsl-agentplane-secrets-backup --operation reconcile --execute`）
4. 从生产机提取运行中的服务配置作为参考（如容器环境变量、挂载卷内容）

## 📅 备份维护 Checklist

- [ ] 确认 1Panel 计划任务 `wsl-agentplane-secrets-backup` 仍存在且运行正常
- [ ] 确认 R2 上备份对象数量不超过保留上限（默认 5 份）
- [ ] 确认 `/data/agentplane/secrets-backup/state.json` 存在且有最近时间戳
- [ ] 确认 secrets 目录结构完整：`secrets/ssh/`、`secrets/services/`、`secrets/hosts/`
- [ ] 确认 inventory 归档是最新的（如有变更）
- [ ] 每季度验证一次从备份恢复的可行性

## 🔗 关联文档

- [Bootstrap Secrets](./bootstrap-secrets.md) — secrets 初始化与骨架生成
- [应用交付主流程](./app-project-delivery-workflow.md) — 恢复后重新部署应用
- [仓库结构规范](../reference/repository-structure.md) — 目录职责与本地态合同
- [当前状态与验证](./current-state-and-validation.md) — 恢复后如何检查状态
- [跨平台规则](../reference/cross-platform.md) — WSL 与 Windows 路径和执行方式
