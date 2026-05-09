---
status: archived
owner: AgentPlane maintainers
last_verified: 2026-04-25
superseded_by: null
audience: both
layer: technical
---

# 📦 应用项目接入 AgentPlane 工作流

结论：应用交付主路径是 `validate-contract → build-artifact → ship-image → render-runtime → deploy → verify → inventory-refresh → doc-sync`。

## 🎯 适用范围

这份 runbook 只描述当前正式支持的应用交付主路径：

- 应用类型：Docker / Compose
- 合同版本：`schema_version: 2`
- 当前样板：`sub2api`
- 正式闭环：`validate-contract -> build-artifact -> ship-image -> render-runtime -> deploy -> verify -> inventory-refresh -> doc-sync`

## 先把路径关系讲清楚

当前真实环境不是“控制面仓库和应用仓库都在同一个 WSL 目录”这么简单。

### 当前样板位置

- AgentPlane Windows 控制面源码：`<repo-root>`
- AgentPlane WSL 目标侧 live checkout：`<repo-root>`
- 源码交付应用仓库：`<app-repo-root>`（当前 active catalog 为空，重新 onboard 后才适用）

### 这意味着什么

- `--repo-root` 始终指 AgentPlane 仓库根。
- Windows 与 WSL 默认共享同一份源码 checkout；WSL 侧验证通过 resolver/backend 路由到同一工作树。
- 应用合同真源仍在应用仓库自己的 `deploy/agentplane/contract*.yaml`。
- catalog 只保存逻辑路径（如 `apps/<app>`）；当正式仓库根不是控制面同级目录时，resolver 负责把逻辑路径解析到实际应用仓库的物理路径。
- `--app-repo-root` 只用于临时 worktree 或显式覆盖，不应该成为长期主路径。

## 当前正式合同要点

`schema_version: 2` 的重点不是“字段更多”，而是把构建与打包拆开：

- `artifact.build_command` 负责生成 runtime artifacts
- `artifact.output_path`、`runtime_os`、`runtime_arch` 固定产物边界
- `packaging.package_command` 负责把已有 artifacts 打成 runtime image
- `runtime` 只描述运行态
- `infra.tenant_resources` 负责声明 app resource 依赖

`sub2api` 当前样板已经按这套 schema 通过了 `wsl`、`prod0-main` 两份合同校验。

## 最小接入清单

### 应用仓库必须交付

- `deploy/build-runtime-artifacts.sh`
- `deploy/package-runtime-image.sh`
- `deploy/Dockerfile.runtime`
- `deploy/agentplane/contract.yaml` 与 target-aware 变体
- 非敏感 env 模板

### AgentPlane 必须已经具备

- 目标环境 inventory
- SSH 与 infra secrets
- 目标侧基础设施对象
- 网站入口对象或 internal ingress 约束

### 4.4 最小本地验证

先过合同门禁，再做任何正式交付预演。

- `agentplane app delivery validate-contract --target <target> --app <app> --repo-root <repo-root>`
- `agentplane app delivery build-artifact --target <target> --app <app> --repo-root <repo-root> --image-tag <tag> --dry-run`
- `agentplane app delivery render-runtime --target <target> --app <app> --repo-root <repo-root> --image-ref <image:tag>`

这是应用接入不变量的最早正式门禁。  
未通过前不进入 `build-artifact`、`ship-image`、`render-runtime`、`deploy`、`rollback` 或 `verify`。  
合同问题必须在这一步暴露，不要等到部署阶段才补救。

### 4.5 新 target 首次纳管补充项

- `agentplane infra network audit <target> --repo-root <repo-root>`
- `agentplane infra network ensure <target> --repo-root <repo-root>`

### 4.6 第二个应用接入前的预检

- `--app-repo-root` 只用于临时 worktree 验证；最终验收必须回到 catalog 指向的正式仓库根。
- `deploy/agentplane/contract*.yaml`、`docs/AGENTPLANE_DEPLOYMENT.*.md`、`inventory/servers/<target>/...` 与 `secrets/hosts/<target>/...` 必须在同一轮变更里收口。
- 退役旧控制面时，不只删脚本和文案，还要删除 `secrets/app-resources/<target>/<app>/*.env` 实体旧文件。

## 正式执行顺序

### 1. 合同校验

```bash
agentplane app delivery validate-contract --target <target> --app <app> --repo-root <repo-root>
```

**预期输出**：

```text
[PASS] schema_version: 2
[PASS] artifact.build_command exists
[PASS] packaging.package_command exists
[PASS] runtime.ports declared
[PASS] infra.tenant_resources valid
```

任何构建、部署、回滚、验证之前，都先过这里。

### 2. 构建交付物

```bash
agentplane app delivery build-artifact --target <target> --app <app> --repo-root <repo-root> --image-tag <tag>
```

当前推荐模式是：

1. WSL/backend 内执行宿主机构建脚本
2. 生成 `dist/oplinux/` 等 runtime artifacts
3. 再走 runtime-only 镜像打包

### 3. 上传镜像

```bash
agentplane app delivery ship-image --target <target> --app <app> --repo-root <repo-root> --image-ref <image:tag>
```

### 4. 渲染运行时

```bash
agentplane app delivery render-runtime --target <target> --app <app> --repo-root <repo-root> --image-ref <image:tag>
```

这里主要看 4 件事：

- 容器名
- host binding
- 依赖容器
- 持久化挂载

### 5. 部署与验证

先预览部署计划：

```bash
agentplane app delivery deploy --target <target> --app <app> --repo-root <repo-root> --image-ref <image:tag> --dry-run
```

**预期输出**：

```text
[PLAN] Target: prod0-main
[PLAN] App: sub2api
[PLAN] Image: ghcr.io/wei-shaw/sub2api:latest
[PLAN] Containers: sub2api-prod, postgres18-prod, redis7-prod
[PLAN] Ports: 0.0.0.0:18080->8080/tcp
[INFO] Dry run complete. Use --execute to apply.
```

确认计划后执行部署：

```bash
agentplane app delivery deploy --target <target> --app <app> --repo-root <repo-root> --image-ref <image:tag> --execute
```

**预期输出**：

```text
[INFO] Deploying sub2api to prod0-main
[INFO] Compose up: sub2api-prod
[INFO] Container started: sub2api-prod
[INFO] Deploy complete
```

然后验证：

```bash
agentplane app delivery verify --target <target> --app <app> --repo-root <repo-root> --execute
```

**预期输出**：

```text
[PASS] Container running: sub2api-prod
[PASS] Health probe: http://127.0.0.1:18080/health -> {"status":"ok"}
[PASS] All checks passed
```

`deploy --dry-run` 是部署计划入口，不是合同校验入口。

生产目标在 `deploy --execute` 和 `verify --execute` 前后，会自动联动 `infra network ensure/audit`。

### 6. 回写

```bash
agentplane app delivery inventory-refresh --target <target> --app <app> --repo-root <repo-root> --write
agentplane app delivery doc-sync --target <target> --app <app> --repo-root <repo-root> --write
```

## `sub2api` 当前样板结论

### `wsl`

- `app object verify` 已通过
- `app delivery verify --execute` 已通过
- 健康探针：`http://127.0.0.1:18080/health`

### `prod0-main`

- `app object verify` 已通过
- `app delivery deploy --dry-run` 已通过
- `app delivery verify --execute` 已通过
- 已验证回环与公网探针都健康

## 当前操作提醒

1. `projection runtime-env plan` 默认脱敏；只有显式 `--reveal-secrets` 才会输出完整 env，不要把 reveal 输出贴到共享日志。
2. `--app-repo-root` 只在临时覆盖时使用；长期状态仍应回到 catalog 解析结果。
3. 目标网络如果未先对齐 `managed_bridge_networks` 与 required container contract，`deploy` 成功也不代表上线安全。

## 下线原则

下线不是删容器，而是撤掉整个对象闭环：

1. 移除 catalog 映射
2. 撤入口
3. 撤运行服务
4. 刷新 ledger / inventory
5. 回写摘要

数据目录和 secrets 退役不在默认下线路径里，必须单独审批。
