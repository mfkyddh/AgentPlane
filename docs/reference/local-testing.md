# 本地测试规范

> **目标**：在推送代码到远程仓库之前，在本地捕获错误，减少 CI 失败。

## 为什么需要本地测试？

| 问题 | 影响 |
|------|------|
| CI 失败后才发现错误 | 浪费时间，延迟合并 |
| 格式问题（ruff）未本地检查 | 多个 commit 修复格式，污染历史 |
| Commit message 不符合规范 | 需要 rebase 修改，团队协作受阻 |
| Secret 泄漏到远程 | 安全风险，需要撤销 commit |

**解决方案**：使用 `pre-commit` 框架，在 `git commit` 和 `git push` 前自动运行检查。

---

## 快速开始

### 1. 安装 pre-commit

```bash
# 使用 uv 安装到开发依赖
uv pip install pre-commit

# 安装 git hooks
pre-commit install
pre-commit install --hook-type pre-push
```

### 2. 运行检查

```bash
# 手动运行所有检查（等同于 CI fast gate）
pre-commit run --all-files

# 仅运行特定 hook
pre-commit run ruff --all-files

# 测试 pre-push 检查（不会真的 push）
git push --dry-run
```

---

## 检查项说明

### pre-commit 阶段（git commit 前）

| Hook | 工具 | 耗时 | 说明 |
|------|------|------|------|
| `ruff` | Ruff linter | < 3s | 检查 Python 代码风格和错误 |
| `ruff-format` | Ruff formatter | < 2s | 自动格式化代码 |
| `validate-commit-msg` | agentplane.cli | < 1s | 验证 commit message 格式 |

**如果失败**：commit 被阻止，修复后重新 commit。

### pre-push 阶段（git push 前）

| Hook | 命令 | 耗时 | 说明 |
|------|------|------|------|
| `fast-test` | `agentplane.cli test fast` | 10-30s | 运行快速测试门 |
| `docs-sanity` | `agentplane.cli repo docs-sanity` | < 5s | 检查文档一致性 |
| `secret-scan` | `agentplane.cli repo secret-scan` | < 5s | 扫描敏感信息泄漏 |

**如果失败**：push 被阻止，修复后重新 push。

---

## 与 CI 的对齐

本地检查项与 CI `fast-gate` 完全对齐：

| 检查项 | 本地 | CI | 说明 |
|--------|------|----|------|
| Commit message 验证 | ✅ pre-commit | ✅ | 格式检查 |
| 快速测试 | ✅ pre-push | ✅ | `test fast` |
| 文档 sanity | ✅ pre-push | ✅ | 链接、格式检查 |
| Secret 扫描 | ✅ pre-push | ✅ | 敏感信息检查 |
| Privacy 扫描 | ❌ | ✅ | 仅 CI 运行 |

**为什么 privacy-scan 不在本地运行？**
- 需要完整 git 历史
- 耗时较长（> 30s）
- 通常在 PR 阶段由 CI 捕获

---

## 跳过检查（谨慎使用）

### 允许跳过的场景

- **紧急 hotfix**：需要立即推送修复
- **WIP 提交**：本地实验，不打算推送
- **文档调整**：仅修改注释或文档

### 如何跳过

```bash
# 跳过 pre-commit 检查
git commit --no-verify -m "your message"

# 跳过 pre-push 检查
git push --no-verify

# 同时跳过
git commit --no-verify && git push --no-verify
```

### ⚠️ 警告

**禁止常规使用 `--no-verify`**：
- 会绕过所有检查，导致坏代码进入远程
- 应在 AGENTS.md 中明确禁止

如果使用了 `--no-verify`，必须在推送后手动运行：
```bash
pre-commit run --all-files
```

---

## 故障排查

### 问题 1：pre-commit 安装失败

```bash
# 检查 pre-commit 是否安装
pre-commit --version

# 如果没有，重新安装
uv pip install pre-commit
```

### 问题 2：hook 运行失败（环境变量问题）

```bash
# 确保在项目根目录
cd /path/to/AgentPlane

# 手动运行 uv run 命令测试
uv run python -m agentplane.cli test fast --tb=short
```

### 问题 3：Windows 上 PowerShell 执行策略

```powershell
# 允许本地脚本执行
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### 问题 4：pre-commit 缓存问题

```bash
# 清理缓存并重新安装
pre-commit clean
pre-commit install --overwrite
```

---

## 最佳实践

1. **提交前先拉取**：避免冲突
   ```bash
   git pull --rebase origin main
   ```

2. **小步提交**：每个逻辑单元独立提交，便于回滚

3. **本地测试通过后再推送**：
   ```bash
   # 提交前
   pre-commit run --all-files
   
   # 推送前
   uv run python -m agentplane.cli test fast
   ```

4. **定期更新 pre-commit hooks**：
   ```bash
   pre-commit autoupdate
   ```

---

## 参考

- [Pre-commit 官方文档](https://pre-commit.com/)
- [AgentPlane CI 配置](../../.github/workflows/ci.yml)
- [Git Hooks 文档](https://git-scm.com/docs/githooks)
