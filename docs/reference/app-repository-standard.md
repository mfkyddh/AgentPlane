---
status: active
owner: AgentPlane maintainers
last_verified: 2026-04-08
superseded_by: null
---

# 应用仓库统一接入规范

本文是新项目与开源二开项目的通用接入标准真源。目标是让应用仓库只负责“把自己打包好”，把正式生产控制面统一收口到 `AgentPlane`。

## 0. 唯一正式入口与生命周期闭环

本规范只定义“标准与边界”，不定义“执行步骤”。执行步骤以 active workflow 为准：见 [应用项目接入 AgentPlane 工作流](../runbooks/app-project-delivery-workflow.md)。

唯一正式入口：

- 所有 onboarding/offboarding 的正式动作都必须从 `AgentPlane` 发起，入口固定为 `uv run python -m agentplane.cli ...`。
- 应用仓库不得维护第二套正式入口脚本（包括但不限于 deploy/rollback/website/inventory/doc-sync）。

生命周期闭环的目标是：新增项目和移除项目都能通过同一条 formal 路径把“真源对象域”和“派生投影”同步到一致状态，避免留下无人认领的 tracked truth。

闭环涉及的对象域与派生链（只给语义，不重复命令细节）：

| 主题 | Add（Onboarding）必须完成 | Remove（Offboarding）必须完成 |
| --- | --- | --- |
| catalog | 把 `target + app` 纳入 `inventory/apps/catalog.json` 的正式映射 | 从 `inventory/apps/catalog.json` 移除映射，确保后续不会被 formal workflow 继续识别 |
| app object | 能被 `ops.cli app object ...` 检索/校验，且台账可刷新 | 在移除映射后，台账刷新不再出现该对象；若仍出现，必须先处理残留引用再继续 |
| app resource | 能被 `ops.cli app resource ...` 检索/校验，且台账可刷新 | 台账刷新后不再出现残留资源引用；如有残留，必须先完成资源退役或解绑 |
| service | 运行服务对象能被 `ops.cli service ...` 计划/核验并与 live state 对齐 | 先确保服务不再承载正式流量与关键任务，再完成服务退役；退役后不得继续出现在受管对象检索里 |
| website | 公网入口对象能被 `ops.cli website ...` 核验并与 1Panel/OpenResty 对齐 | 先完成入口撤销或下线（证书、反代、域名解析等），再刷新网站台账避免“入口已死但对象仍在” |
| projection | `ops.cli projection runtime-env ...` 与 `ops.cli projection ledger refresh` 能把派生物写回到一致状态 | 在对象移除后，projection 必须重新生成或清理派生物，避免旧派生物继续影响 inventory 或验证 |
| inventory | `app delivery inventory-refresh` 后，`inventory/servers/<target>/inventory.json` 反映新增对象 | `inventory-refresh` 后，inventory 不再包含已移除对象的状态残影 |
| docs | `app delivery doc-sync` 后，AgentPlane 与应用仓库摘要一致 | `doc-sync` 后，人类可读摘要不再宣称该项目仍受管或仍有公网入口 |

上述“必须完成”的含义是：同一次 lifecycle 变更必须把所有域走完闭环；不允许只改一半（例如只删容器，不删 catalog；或只关入口，不更新 inventory/doc）。

## 1. Git 远程与版本治理

| 项目类型 | 远程规范 | 说明 |
| --- | --- | --- |
| 新项目 | 只保留 `origin` | `origin` 指向你的可写主仓库。 |
| 开源二开项目 | 固定为 `origin + upstream` | `origin` 指向你自己的可写仓库；`upstream` 指向官方只读源。 |

固定规则：

- 默认主分支统一为 `main`；若上游默认分支已有稳定命名，优先跟随上游。
- 官方同步固定走同步分支：`sync/upstream-YYYYMMDD`。
- 不在已发布主线上反复 `rebase upstream/main`。
- 二开版本统一使用：
  - `FORK_VERSION=zzz.<yyyymmdd>.v<n>.g<gitsha>`
  - `DELIVERY_VERSION=<upstream>+zzz.<yyyymmdd>.v<n>.g<gitsha>`
  - `IMAGE_TAG=<upstream>-zzz.<yyyymmdd>.v<n>.g<gitsha>`

## 2. 推荐目录骨架

```text
README.md
src/ or frontend/ + backend/
tests/
deploy/
  build-runtime-artifacts.sh
  package-runtime-image.sh
  Dockerfile.runtime
  docker-entrypoint.sh
  prod/
    app-prod.env.example
  op/
    contract.yaml
docs/
  AGENTPLANE_DEPLOYMENT.wsl.md
  AGENTPLANE_DEPLOYMENT.prod0-main.md
scripts/                 # 只放本地开发辅助脚本
dist/
  oplinux/
tmp/
.worktrees/
```

约束：

- `deploy/` 固定承载交付资产。
- `scripts/` 不得承载正式部署、正式回滚、正式入口发布逻辑。
- `dist/oplinux/` 是正式打包唯一制品目录。
- `tmp/`、`.worktrees/`、真实 `.env`、构建产物必须进入 `.gitignore`。

## 3. Secrets 与模板边界

| 内容 | 放在 `AgentPlane` | 放在应用仓库 |
| --- | --- | --- |
| 真实 secrets、SSH、`.pem`、管理凭据 | 是 | 否 |
| 应用运行时非敏感模板 | 否 | 是 |
| 正式 inventory、正式回滚材料 | 是 | 否 |
| `deploy/agentplane/contract.yaml` | 否 | 是 |
| 非敏感部署摘要 | 由 `AgentPlane` 回写 | 是 |

模板注释统一优先回答 3 个问题：

1. 复制到哪里
2. 是否真实敏感
3. 是否 canonical 或 legacy reference

## 4. `AGENTS.md` 与 Codex 环境

应用仓库根 `AGENTS.md` 只保留 6 段：

1. `Scope`
2. `Repo Map`
3. `Standard Commands`
4. `Working Rules`
5. `Definition Of Done`
6. `Docs`

Codex 本地环境固定放在 `.codex/environments/`：

- `environment.toml`：薄入口路由
- `setup/`：轻量幂等初始化
- `actions/`：常用手动动作
- `lib/`：公用探测逻辑

默认 actions：

- `Bootstrap`
- `Test`
- `Lint`
- `Build`
- `Dev`
- `Compose Up`
- `Compose Logs`
- `Smoke`

## 5. Win + WSL + 远程 Linux

- 默认 `WSL-first`。
- Git、构建、测试、`uv`、`pnpm`、`docker compose`、`ssh`、远端 Linux 操作都在 WSL 执行。
- 人在宿主机侧时，只负责把命令送进 WSL，不重写 Linux 命令。
- 远端多语句任务统一先落成 Linux 脚本，再走正式 CLI 执行。

## 6. 与 `AgentPlane` 的职责边界

应用仓库负责：

- 业务代码
- 测试
- runtime 构建资产
- 非敏感模板
- `deploy/agentplane/contract.yaml`

`AgentPlane` 负责：

- 正式部署
- 正式切换
- 正式回滚
- 正式入口
- 正式验证
- `inventory / ledger / doc-sync`

应用仓库禁止存在第二控制面脚本，例如：

- `deploy-prod.sh`
- `rollback-prod.sh`
- `publish-website.sh`
- `issue-cert.sh`
- `sync-inventory.sh`

## 7. 发布与回滚

正式闭环固定为：

`plan -> apply -> verify -> ledger -> inventory -> doc-sync`

新增统一规则：

- 发布前先创建回滚态容器。
- 回滚态是发布开始前最后一个已知良好、可直接重新接管正式流量的运行态。
- 新版本验证成功并经过最小观察窗口后，再删除旧容器。

## 8. 合理工作流

1. 建立 `.worktrees/<branch>/` 隔离工作树。
2. 在应用仓库完成代码、测试、构建资产、合同和模板。
3. 本地通过最小交接门槛：
   - 仓库测试
   - runtime 制品构建
   - 镜像可 inspect
   - 合同可校验
4. 交给 `AgentPlane` 执行正式部署、验证、回写。
5. 只有 `verify` 通过后，才刷新 `inventory` 与摘要。

## 9. 第二个应用快速接入硬约束

如果目标是让第二个 Docker / Compose 应用按同一 formal 路径快速接入，而不是重复 `Sub2API` 那轮返工，首轮接入就必须同时满足以下约束：

- 如果 target 之间入口、依赖或回退面不同，一开始就提供 target-aware 合同与摘要文件；不要先拿单一 `contract.yaml` 或单一部署摘要硬顶，再靠后续补丁分叉。
- 真实 app resource secrets 从首轮接入开始就固定放在 `secrets/hosts/<target>/apps/<app>/resources/`；`secrets/services/...` 只作为 runtime projection，不反向充当真源。
- 不为新接入项目再落一份 `secrets/app-resources/<target>/<app>/` 实体文件；如果是在收敛存量项目，legacy 文件必须在接入完成前删掉并加回归门禁。
- 最终验收必须回到 catalog 指向的正式仓库根执行；临时 worktree 可以用于开发和预检，但不能代替正式 `validate-contract` / `inventory-refresh` / `doc-sync` 验收。
