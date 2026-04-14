---
status: active
owner: AgentPlane maintainers
last_verified: 2026-04-02
superseded_by: null
---

# 应用交付版本规范

本文是 `AgentPlane` 管理的 Docker/Compose 应用统一二开版本规范 reference 真源。本文只定义长期稳定的版本号、镜像 tag 与 CLI 生成规则，不展开具体发布步骤或环境切换 runbook。

## 规则

- `FORK_VERSION=zzz.<yyyymmdd>.v<n>.g<gitsha>`
- `DELIVERY_VERSION=<upstream>+zzz.<yyyymmdd>.v<n>.g<gitsha>`
- `IMAGE_TAG=<upstream>-zzz.<yyyymmdd>.v<n>.g<gitsha>`

其中：

- `<upstream>`：应用上游版本
- `<yyyymmdd>`：构建日期
- `<n>`：同一应用、同一 `<upstream>`、同一天内的二开递增序号
- `<gitsha>`：发布提交短 SHA，不带额外分隔符，统一前缀为 `g`

## 应用合同

`deploy/agentplane/contract.yaml` 中的 `packaging.image_tag_rule` 统一写为：

```yaml
packaging:
  image_tag_rule: <upstream>-zzz.<yyyymmdd>.v<n>.g<gitsha>
```

这里表达的是 tag 规则本身，不包含镜像名。实际镜像引用仍为 `<image_name>:<image_tag>`。

## CLI 行为

- `uv run python -m agentplane.cli app delivery build-artifact --dry-run` 会尽量输出推荐的：
  - `fork_version`
  - `delivery_version`
  - `image_tag`
- `uv run python -m agentplane.cli app delivery build-artifact --auto-version` 会使用这套规则自动生成本次构建的 `IMAGE_TAG`
- 若应用仓库无法提供上游版本或 git short SHA，CLI 不会伪造版本号；自动生成会直接失败

## 序号来源

- `v<n>` 的最小可追溯来源是 `AgentPlane/tmp/operation-ledger/*.jsonl`
- 以同一 `app_id`、同一 `upstream_version`、同一 `build_date` 的既有 `build-artifact` 记录为基线，下一次自动生成时取 `max(n)+1`
- 无既有记录时，首个序号为 `v1`

## Phase 4 / Lane 12 focused acceptance（只读与 dry-run）

本节用于 Phase 4 / Lane 12 的 focused acceptance 资产约束。验收命令仅允许只读或 dry-run，不在该车道执行写入型流程。

- `uv run python -m agentplane.cli host automation search wsl --repo-root <repo-root>`
- `uv run python -m agentplane.cli projection ledger refresh --target wsl --repo-root <repo-root>`
- `uv run python -m agentplane.cli app delivery build-artifact --target <target> --app <app> --repo-root <repo-root> --dry-run`
