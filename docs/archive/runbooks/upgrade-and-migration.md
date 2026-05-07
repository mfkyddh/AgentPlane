---
status: archived
owner: AgentPlane maintainers
last_verified: 2026-04-30
superseded_by: null
audience: both
layer: technical
---

# 🛠️ 升级与迁移指南

结论：AgentPlane 升级遵循 **pull → verify → apply → verify** 闭环。Breaking change 通过 `CHANGELOG.md` 和 `release-check` 提前发现，数据迁移通过 `agentplane` CLI 执行，回滚通过 Git tag 切换。

## 🎯 适用场景

| 场景 | 是否适用 |
| --- | --- |
| 升级 AgentPlane 到新版本 | ✅ |
| 处理 breaking change | ✅ |
| 迁移 inventory / projection 数据 | ✅ |
| 升级后验证完整性 | ✅ |
| 回滚到旧版本 | ✅ |
| 首次安装 AgentPlane | ❌ → [bootstrap-secrets.md](bootstrap-secrets.md) |

## 🧭 升级流程概览

```text
检查当前版本 → 拉取新版本 → 运行 release-check → 处理 breaking change → 执行迁移 → 验证 → 提交
```

---

## 1. 版本升级流程

### 1.1 检查当前版本

```bash
# 查看当前安装版本
agentplane --version

# 或通过 pip 查看
uv pip show agentplane
```

### 1.2 拉取新版本

```bash
# 拉取最新代码
git fetch origin
git pull origin main

# 查看变更日志
git log --oneline HEAD@{1}..HEAD

# 或查看 CHANGELOG
cat CHANGELOG.md
```

### 1.3 运行发布检查

```bash
# 确认新版本通过所有门禁
agentplane repo release-check --repo-root .
```

**预期输出**：

```text
[PASS] Lint check
[PASS] Default tests
[PASS] Coverage generation
[PASS] Build check
[PASS] Dependency audit
[PASS] Privacy scan
[PASS] Working tree clean
```

### 1.4 重新安装（如需要）

```bash
# 方式一：全局安装
uv tool install -e .

# 方式二：无需全局安装
uv run agentplane --help
```

---

## 2. Breaking Change 处理

### 2.1 识别 Breaking Change

在升级前检查以下来源：

| 来源 | 检查方式 |
| --- | --- |
| `CHANGELOG.md` | 查看 `[BREAKING]` 标记 |
| Git commit message | 查看 `feat!:` 或 `fix!:` 前缀 |
| `release-check` 输出 | 检查是否有 FAIL 项 |
| 架构决策记录 | `docs/architecture/decisions/` |

### 2.2 Breaking Change 分类处理

| 类型 | 处理方式 |
| --- | --- |
| CLI 命令重命名 | 更新脚本、skill、文档中的命令引用 |
| 配置格式变更 | 按迁移指南更新配置文件 |
| Inventory schema 变更 | 运行 `agentplane projection ledger migrate` |
| Provider API 变更 | 更新 provider 配置，重新验证连接 |
| Runtime backend 变更 | 更新 backend 配置，重新验证连接 |

### 2.3 处理步骤

```bash
# 1. 查看具体变更
git diff HEAD@{1}..HEAD -- agentplane/cli/
git diff HEAD@{1}..HEAD -- agentplane/domain/

# 2. 检查受影响的 skill
agentplane repo skills check --repo-root .

# 3. 检查文档一致性
agentplane repo docs-sanity --repo-root .
```

---

## 3. 数据迁移步骤

### 3.1 迁移前备份

```bash
# 备份当前 inventory
cp -r inventory/ inventory.backup.$(date +%Y%m%d)/

# 备份 secrets 结构（不包含真实值）
ls -la secrets/ > tmp/secrets-structure-backup.txt

# 备份当前 Git 状态
git stash list
git tag -l | tail -5
```

### 3.2 Inventory 迁移

```bash
# 检查当前 inventory 状态
agentplane projection ledger status --repo-root .

# 如有 schema 变更，运行迁移
agentplane projection ledger migrate --repo-root .

# 验证迁移结果
agentplane projection ledger verify --repo-root .
```

**预期输出**：

```text
[INFO] Migration started
[INFO] Migrated 3 ledger entries
[INFO] Migration completed
[PASS] Ledger verification
```

### 3.3 Projection 迁移

```bash
# 刷新所有 projection
agentplane projection refresh --repo-root .

# 验证 projection 一致性
agentplane projection verify --repo-root .
```

### 3.4 配置迁移

```bash
# 检查配置文件格式
agentplane bootstrap inspect-local --repo-root .

# 如有配置格式变更，更新对应文件
# 参考 CHANGELOG.md 中的具体说明
```

---

## 4. 回滚策略

### 4.1 回滚前判断

| 情况 | 回滚方式 |
| --- | --- |
| 代码问题，未修改 inventory | `git checkout` 到旧版本 |
| Inventory 已迁移 | 从备份恢复 + Git checkout |
| Provider 配置已变更 | 恢复配置文件 + Git checkout |
| 已有线上流量 | 暂停操作，评估影响后决定 |

### 4.2 代码回滚

```bash
# 查看可用的版本 tag
git tag -l

# 回滚到指定版本
git checkout v0.1.0

# 重新安装
uv tool install -e .
```

### 4.3 Inventory 回滚

```bash
# 恢复 inventory 备份
rm -rf inventory/
cp -r inventory.backup.YYYYMMDD/ inventory/

# 验证恢复结果
agentplane projection ledger status --repo-root .
```

### 4.4 完整回滚流程

```bash
# 1. 停止所有操作
# 2. 恢复 inventory
cp -r inventory.backup.YYYYMMDD/ inventory/

# 3. 回滚代码
git checkout v0.1.0

# 4. 重新安装
uv tool install -e .

# 5. 验证回滚
agentplane repo health-check --repo-root .
agentplane projection ledger status --repo-root .
```

---

## 5. 升级前检查清单

在执行升级前，逐项确认：

| # | 检查项 | 命令 | 预期结果 |
| --- | --- | --- | --- |
| 1 | 当前版本已记录 | `agentplane --version` | 记录版本号 |
| 2 | 工作区干净 | `git status --short` | 无未提交变更 |
| 3 | Inventory 已备份 | `ls inventory.backup.*` | 备份目录存在 |
| 4 | Secrets 结构已记录 | `ls secrets/` | 目录结构清晰 |
| 5 | 当前测试通过 | `uv run python -m pytest` | 全部 PASS |
| 6 | 当前健康检查通过 | `agentplane repo health-check --repo-root .` | 全部 PASS |
| 7 | 已阅读 CHANGELOG | `cat CHANGELOG.md` | 了解本次变更 |
| 8 | 已识别 breaking change | 检查 `[BREAKING]` 标记 | 已知悉 |

---

## 6. 升级后验证

### 6.1 基础验证

```bash
# 1. CLI 可用性
agentplane --help

# 2. 版本确认
agentplane --version

# 3. 健康检查
agentplane repo health-check --repo-root .

# 4. 测试通过
uv run python -m pytest
```

**预期输出**：

```text
[PASS] Repository structure
[PASS] docs-sanity 链接检查
[PASS] 入口漂移检查
```

### 6.2 功能验证

```bash
# 1. Skill 完整性
agentplane repo skills check --repo-root .

# 2. 文档一致性
agentplane repo docs-sanity --repo-root .

# 3. Inventory 一致性
agentplane projection ledger status --repo-root .

# 4. Backend 连通性（如有 remote target）
agentplane infra audit wsl --repo-root .
```

### 6.3 现场验证（如有 live target）

```bash
# 运行 live integration gate
agentplane infra live-gate --repo-root .
```

> ⚠️ live gate 会连接真实环境，仅在确认升级无误后执行。

### 6.4 验证完成标准

| 检查项 | 通过标准 |
| --- | --- |
| CLI 可用 | `agentplane --help` 正常输出 |
| 健康检查 | `repo health-check` 全部 PASS |
| 测试通过 | `pytest` 全部 PASS |
| Skill 完整 | `repo skills check` 无 ERROR |
| 文档一致 | `repo docs-sanity` 无断链 |
| Inventory 正常 | `projection ledger status` 无异常 |

---

## 7. 特殊场景

### 7.1 跨大版本升级

如果跨越多个大版本（如 v0.1 → v0.3），需要：

1. 逐版本阅读 `CHANGELOG.md`，识别所有 breaking change
2. 按版本顺序执行迁移，不要跳步
3. 每个版本升级后运行完整验证

### 7.2 Provider 升级

Provider（如 1Panel、Cloudflare）API 变更时：

```bash
# 1. 检查 provider 版本
agentplane infra provider status --repo-root .

# 2. 更新 provider 配置
# 参考 docs/reference/onepanel-api-contract.md

# 3. 验证 provider 连接
agentplane infra provider verify --repo-root .
```

### 7.3 Runtime Backend 升级

Runtime backend（如 WSL、SSH）变更时：

```bash
# 1. 检查 backend 状态
agentplane runtime backend status --repo-root .

# 2. 验证 backend 连通性
agentplane runtime backend verify --repo-root .
```

---

## 🔗 关联文档

| 文档 | 说明 |
| --- | --- |
| [release-process.md](../reference/release-process.md) | 发布流程和健康检查规范 |
| [repository-structure.md](../reference/repository-structure.md) | 仓库结构和文件放置规则 |
| [bootstrap-secrets.md](bootstrap-secrets.md) | 首次安装引导 |
| [current-state-and-validation.md](current-state-and-validation.md) | 当前状态和验证快照 |
| [CHANGELOG.md](../../CHANGELOG.md) | 版本变更日志 |

---

## 📌 升级原则

1. **先备份再升级** — Inventory 和配置必须有备份
2. **先验证再应用** — `release-check` 通过后再执行迁移
3. **先小范围再全局** — 如有多个 target，先在 wsl 验证再推广
4. **先读 CHANGELOG 再操作** — 了解 breaking change 再动手
5. **升级后必验证** — 健康检查 + 测试 + Skill 检查缺一不可
