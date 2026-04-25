---
status: active
owner: AgentPlane maintainers
last_verified: 2026-04-12
superseded_by: null
audience: agent

---

# 应用仓库统一接入规范

结论：应用仓库接入 AgentPlane 的目录结构、合同字段和交付物标准。

本文是 Agent-first 控制面模板下的新项目与开源二开项目通用接入标准。应用仓库只负责代码、构建资产、合同与非敏感模板；控制面模板仓库负责 bootstrap、正式执行、验证、回写与对外 runbook。

## 0. 唯一正式入口与生命周期闭环

本规范只定义标准与边界，不定义具体执行步骤。执行步骤以 active workflow 为准：见 [应用项目接入 AgentPlane 工作流](../runbooks/app-project-delivery-workflow.md)。

唯一正式入口：

- 所有 onboarding / offboarding 的正式动作都必须从 `AgentPlane` 发起，入口固定为 `agentplane ...`。
- 应用仓库不得维护第二套正式入口脚本；不要再维护第二控制面。

生命周期闭环的目标是：新增项目和移除项目都能通过同一条 formal 路径把真源对象域与派生投影同步到一致状态，避免留下无人认领的 tracked truth。

闭环涉及的对象域与派生链：

| 主题 | Add（Onboarding）必须完成 | Remove（Offboarding）必须完成 |
| --- | --- | --- |
| catalog | 把 `target + app` 纳入 `inventory/apps/catalog.json` 的正式映射 | 从 `inventory/apps/catalog.json` 移除映射，确保后续不会被 formal workflow 继续识别 |
| app object | 能被 `agentplane.cli app object ...` 检索/校验，且台账可刷新 | 在移除映射后，台账刷新不再出现该对象；若仍出现，必须先处理残留引用再继续 |
| app resource | 能被 `agentplane.cli app resource ...` 检索/校验，且台账可刷新 | 台账刷新后不再出现残留资源引用；如有残留，必须先完成资源退役或解绑 |
| service | 运行服务对象能被 `agentplane.cli service ...` 计划/核验并与 live state 对齐 | 先确保服务不再承载正式流量与关键任务，再完成服务退役；退役后不得继续出现在受管对象检索里 |
| ingress | 公网入口对象能被 `agentplane.cli ingress ...` 核验并与 provider 对齐 | 先完成入口撤销或下线（证书、反代、域名解析等），再刷新入口台账避免“入口已死但对象仍在” |
| projection | `agentplane.cli projection runtime-env ...` 与 `agentplane.cli projection ledger refresh` 能把派生物写回到一致状态 | 在对象移除后，projection 必须重新生成或清理派生物，避免旧派生物继续影响 inventory 或验证 |
| inventory | `app delivery inventory-refresh` 后，`inventory/servers/<target>/inventory.json` 反映新增对象 | `inventory-refresh` 后，inventory 不再包含已移除对象的状态残影 |
| docs | `app delivery doc-sync` 后，控制面模板仓库与应用仓库摘要一致 | `doc-sync` 后，人类可读摘要不再宣称该项目仍受管或仍有公网入口 |

上述“必须完成”的含义是：同一次 lifecycle 变更必须把所有域走完闭环；不允许只改一半。

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
  agentplane/
    contract.yaml
docs/
  AGENTPLANE_DEPLOYMENT.<target>.md
scripts/                 # 只放本地开发辅助脚本
dist/
tmp/
.worktrees/
```

约束：

- `deploy/` 固定承载交付资产。
- `scripts/` 不得承载正式部署、正式回滚、正式入口发布逻辑。
- 真实 `.env`、构建产物、`tmp/`、`.worktrees/` 必须进入 `.gitignore`。
- `deploy/agentplane/contract.yaml` 是应用仓库交给控制面模板仓库的正式交接点。

## 3. Secrets 与模板边界

| 内容 | 放在控制面模板仓库 | 放在应用仓库 |
| --- | --- | --- |
| 真实 secrets、SSH、`.pem`、管理凭据 | 是 | 否 |
| 应用运行时非敏感模板 | 否 | 是 |
| 正式 inventory、正式回滚材料 | 是 | 否 |
| `deploy/agentplane/contract.yaml` | 否 | 是 |
| 非敏感部署摘要 | 由控制面模板仓库回写 | 是 |

模板注释优先回答 3 个问题：

1. 复制到哪里
2. 是否真实敏感
3. 是逻辑路径还是遗留物理路径

## 4. `AGENTS.md` 与 Codex 环境

应用仓库根 `AGENTS.md` 只保留 6 段：

1. `Scope`
2. `Repo Map`
3. `Standard Commands`
4. `Working Rules`
5. `Definition Of Done`
6. `Docs`

## 5. Host Entry / Backend-Aware 规则

- 默认采用 host-entry-first, backend-aware。
- 如果控制面和源码都在同一宿主，直接使用宿主原生命令。
- 如果控制面在 Windows、源码在 Linux backend，入口仍是 `pwsh`，源码绑定动作委托到对应 backend。
- Windows 上的 Linux-only 动作优先 `wsl.exe -e <program> <args...>`；只有确实需要 shell 特性时才退回 `bash -lc`。
- 远端 Linux 正式任务统一走 `agentplane ...`，不要在应用仓库里自建远端执行旁路。

## 6. 与控制面模板仓库的职责边界

应用仓库负责：

- 业务代码
- 测试
- runtime 构建资产
- 非敏感模板
- `deploy/agentplane/contract.yaml`

控制面模板仓库负责：

- bootstrap
- 正式部署
- 正式切换
- 正式回滚
- 正式验证
- `ledger / inventory / doc-sync`
- 对外 runbook 与 repo-owned skills

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
