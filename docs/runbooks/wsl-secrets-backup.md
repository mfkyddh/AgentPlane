# WSL Secrets Backup Runbook

## Purpose

统一管理 WSL 本机 `secrets/` 目录的加密备份。正式执行入口是仓库 CLI；1Panel 计划任务只负责定时触发，不承载业务逻辑。

## Scope

| 项目 | 值 |
| --- | --- |
| 真源目录 | `<repo-root>/secrets` |
| 状态文件 | `/data/agentplane/secrets-backup/state.json` |
| 临时目录 | `/tmp/agentplane-secrets-backup` |
| 调度器 | WSL 本机 `1Panel` 计划任务 `wsl-agentplane-secrets-backup` |
| 控制面仓库 | `<repo-root>` |
| 远端桶 | `AgentPlane_Backups` |
| 对象前缀 | `backups/agentplane/secrets-main/` |

## Execution Entry

任务 env 文件是 `secrets/services/secrets-backup.r2.wsl.env`。
若本机 secrets 布局发生调整，先执行 `agentplane infra secrets sync-layout wsl --repo-root <repo-root> --write`，再重新核验自动化任务。

手动执行正式入口：

```bash
env -C <repo-root> agentplane infra automation apply wsl --name wsl-agentplane-secrets-backup --operation run --execute
```

核验并回写 WSL 本机计划任务：

```bash
env -C <repo-root> agentplane infra automation verify wsl --name wsl-agentplane-secrets-backup --repo-root <repo-root>
env -C <repo-root> agentplane infra automation apply wsl --name wsl-agentplane-secrets-backup --operation reconcile --execute --repo-root <repo-root>
```

只读核对计划任务对象是否仍存在：

```bash
env -C <repo-root> agentplane onepanel \
  --env wsl \
  cronjob search \
  --info wsl-agentplane-secrets-backup
```

## Expected Results

- `ok_no_changes`
  - 快速指纹或强指纹判断 `secrets/` 无内容变化，不上传新备份
- `ok_uploaded`
  - 已生成加密备份、上传到 R2，并完成旧对象裁剪
- `failed_precheck`
  - 源目录缺失或配置不完整
- `failed_runtime`
  - 打包、加密、上传或远端清理失败

## 1Panel Task Baseline

- 任务名：`wsl-agentplane-secrets-backup`
- 周期：每 5 小时一次
- Cron：`0 */5 * * *`
- 工作目录：`<repo-root>`
- 命令：`agentplane infra automation apply wsl --name wsl-agentplane-secrets-backup --operation run --execute`
- 类型：`shell`
- executor：`bash`
- scriptMode：`input`
- user：`root`

## Verification

建议每次调整后执行最小验证：

```bash
env -C <repo-root> uv run python -m pytest \
  tests/secret_management/test_secrets_backup_r2.py \
  tests/repository/test_cli_entrypoints.py \
  tests/host/test_host_automation.py \
  tests/inventory/test_inventory_generation.py \
  tests/repository/test_docs_no_legacy_terms.py -q

env -C <repo-root> agentplane infra automation apply wsl --name wsl-agentplane-secrets-backup --operation run --execute
env -C <repo-root> agentplane infra automation apply wsl --name wsl-agentplane-secrets-backup --operation reconcile --execute --repo-root <repo-root>
env -C <repo-root> agentplane onepanel --env wsl cronjob search --info wsl-agentplane-secrets-backup
```

## Common Failures

### Upload Failed

现象：

- 返回 `failed_runtime`
- `reason` 中包含 R2 `PUT` 或网络错误

处理：

```bash
env -C <repo-root> agentplane infra automation apply wsl --name wsl-agentplane-secrets-backup --operation run --execute
```

必要时核对 `secrets/services/secrets-backup.r2.wsl.env`。
若要核对任务 env 文件，请查看 `secrets/services/secrets-backup.r2.wsl.env`。

### Local State Mismatch

现象：

- 预期无变化但重复上传

处理：

```bash
cat /data/agentplane/secrets-backup/state.json
find <repo-root>/secrets -type f | sort
```

确认 `secrets/hosts/wsl` 是否存在实际内容变化，而不是只看时间戳。

### Old Remote Objects Not Pruned

现象：

- R2 前缀下对象数超过 5

处理：

先手动重跑正式 CLI 入口。若仍超出 5 份，检查 stdout 中的 `deleted_old_backups` 与 R2 列表结果。

## Manual Inspection

以下内容只能作为只读补充：

- 打开 WSL 本机 1Panel 面板查看 cronjob 最近执行记录
- 如需进一步核对对象层状态，继续使用 `agentplane onepanel --env wsl cronjob ...`
