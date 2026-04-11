# NewAPI OP_Linux Isolation Handoff

## 1. 目标

在新会话中继续完成 `new-api` 按隔离式基础设施模型接入 `OP_Linux` 的后续工作。

当前范围已经覆盖：

- `new-api` 在 WSL 下的初始化安装
- PostgreSQL / Redis 租户化配置
- `OP_Linux` 的 WSL / prod0 target-aware 交付链
- 二开版本号与 Docker tag 规则
- 仓库内 `.worktrees/` 默认规范
- `Node => pnpm`、`Python => uv` 规范落地

## 2. 当前工作区

继续工作的两个 worktree：

- `OP_Linux`：`/root/work/OP_Linux/.worktrees/codex-newapi-oplinux-isolation`
- `new-api`：`/root/work/new-api/.worktrees/codex-newapi-oplinux-isolation`

当前分支：

- `OP_Linux`：`codex/newapi-oplinux-isolation`
- `new-api`：`codex/newapi-oplinux-isolation`

最近提交：

- `new-api`：`1c0dd30 feat: onboard oplinux runtime packaging for newapi`
- `OP_Linux`：`2790a0a feat: add newapi wsl delivery workflow`

两个 worktree 当前都是 clean。

## 3. 已完成结果

### 3.1 `new-api` 已完成

- 默认 worktree 已改为仓库内 `.worktrees/`，并写入 `.gitignore`
- 已新增 runtime 打包链路：
  - `deploy/compute-oplinux-version.sh`
  - `deploy/build-runtime-artifacts.sh`
  - `deploy/package-runtime-image.sh`
  - `deploy/Dockerfile.runtime`
- 已把 Node 构建依赖切到 `pnpm`
- 已新增 `web/.npmrc`，使用 `node-linker=hoisted`
- 已生成 `web/pnpm-lock.yaml`
- 已修复构建兼容问题：
  - `react-icons` 中 `SiLinkedin` 改为 `FaLinkedin`
  - `Semi UI` 样式导入兼容 `pnpm`
- 合同已补全 `infra.tenant_resources.postgres` / `redis`
- 二开版本规则已定为：
  - `FORK_VERSION=zzz.<yyyymmdd>.v<n>.g<gitsha>`
  - `DELIVERY_VERSION=<upstream>+zzz.<yyyymmdd>.v<n>.g<gitsha>`
  - `IMAGE_TAG=<upstream>-zzz.<yyyymmdd>.v<n>.g<gitsha>`

### 3.2 `OP_Linux` 已完成

- 顶层规范已新增：
  - 管理项目默认使用仓库内 `.worktrees/`
  - Node 项目依赖优先 `pnpm`
  - Python 项目依赖优先 `uv`
- 已补齐 `newapi` 的 WSL compose 模板：
  - `infra/compose/newapi/docker-compose.wsl.yml`
- 已补齐模板和台账：
  - `templates/services/newapi.wsl.env.example`
  - `templates/services/newapi.prod0.env.example`
  - `inventory/servers/wsl/app-resources.json`
  - `inventory/servers/prod0-main/app-resources.json`
- 已把以下命令做成 target-aware：
  - `app validate-contract`
  - `app render-runtime`
  - `app verify`
  - `app inventory-refresh`
  - `projection runtime-env apply`
- `app_resource_state.py` 已支持 worktree 下回退到 common `secrets/`

## 4. 当前运行状态

WSL 当前在线容器：

- `postgres18-dev`
- `redis7-dev`
- `minio-dev`
- `newapi-dev`

当前 `newapi-dev` 镜像：

- `newapi-prod:v0.11.9-alpha.2-zzz.20260326.v1.gbd2a7f6d7a17`

当前版本串：

- `v0.11.9-alpha.2+zzz.20260326.v1.gbd2a7f6d7a17`

当前健康检查：

- `http://127.0.0.1:3000/api/status` 已返回成功

## 5. 本地 secrets / tenant 状态

这些文件已经在主仓库真实路径生成，但未提交：

- `/root/work/OP_Linux/secrets/services/newapi.wsl.env`
- `/root/work/OP_Linux/secrets/services/newapi.prod0.env`
- `/root/work/OP_Linux/secrets/app-resources/wsl/newapi/postgres.env`
- `/root/work/OP_Linux/secrets/app-resources/wsl/newapi/redis.env`
- `/root/work/OP_Linux/secrets/app-resources/prod0-main/newapi/postgres.env`
- `/root/work/OP_Linux/secrets/app-resources/prod0-main/newapi/redis.env`

WSL PostgreSQL 已创建：

- database: `newapi_wsl`
- user: `newapi_wsl`

WSL Redis 当前使用：

- host: `redis7-dev`
- db: `2`
- key prefix: `newapi:wsl:`

## 6. 已验证命令

### 6.1 `new-api`

在 `/root/work/new-api/.worktrees/codex-newapi-oplinux-isolation` 已验证：

```bash
bash tests/test_oplinux_versioning.sh
bash tests/test_oplinux_versioning_fallback.sh
bash tests/test_build_runtime_artifacts.sh
bash deploy/build-runtime-artifacts.sh
bash deploy/package-runtime-image.sh
```

### 6.2 `OP_Linux`

在 `/root/work/OP_Linux/.worktrees/codex-newapi-oplinux-isolation` 已验证：

```bash
uv run python -m pytest tests/test_app_cli.py -q -k 'newapi or secret_file_resolution_from_common_secrets_root_in_worktree'
uv run python -m pytest tests/test_prod0_postgres_app_resource_audit.py -q -k 'newapi or render_env_for_newapi_does_not_require_minio_secret'
uv run python -m pytest tests/test_newapi_compose_layout.py -q
uv run python -m ops.cli app resource verify --target wsl --repo-root /root/work/OP_Linux/.worktrees/codex-newapi-oplinux-isolation
uv run python -m ops.cli app resource verify --target prod0-main --repo-root /root/work/OP_Linux/.worktrees/codex-newapi-oplinux-isolation
uv run python -m ops.cli app validate-contract --contract /root/work/new-api/.worktrees/codex-newapi-oplinux-isolation/deploy/op/contract.yaml --repo-root /root/work/OP_Linux/.worktrees/codex-newapi-oplinux-isolation --target wsl
uv run python -m ops.cli app render-runtime --contract /root/work/new-api/.worktrees/codex-newapi-oplinux-isolation/deploy/op/contract.yaml --repo-root /root/work/OP_Linux/.worktrees/codex-newapi-oplinux-isolation --target wsl --image-ref newapi-prod:verify
uv run python -m ops.cli app verify wsl --contract /root/work/new-api/.worktrees/codex-newapi-oplinux-isolation/deploy/op/contract.yaml --repo-root /root/work/OP_Linux/.worktrees/codex-newapi-oplinux-isolation
uv run python -m ops.cli app inventory-refresh wsl --contract /root/work/new-api/.worktrees/codex-newapi-oplinux-isolation/deploy/op/contract.yaml --repo-root /root/work/OP_Linux/.worktrees/codex-newapi-oplinux-isolation --write
```

### 6.3 WSL 启动验证

```bash
cd /root/work/new-api/.worktrees/codex-newapi-oplinux-isolation
eval "$(bash deploy/compute-oplinux-version.sh)"
NEWAPI_IMAGE_REF="newapi-prod:${IMAGE_TAG}" docker compose -f /root/work/OP_Linux/.worktrees/codex-newapi-oplinux-isolation/infra/compose/newapi/docker-compose.wsl.yml up -d
curl -fsS http://127.0.0.1:3000/api/status
```

## 7. 剩余工作

下一会话优先继续这些事项：

1. 准备 `prod0-main` 的正式交付动作
2. 使用现有网站对象 `newapi`，不要新建 OpenResty 站点
3. 执行正式链路：
   - `app render-runtime --target prod0-main`
   - `app ship-image prod0-main`
   - 生成 deploy / rollback 计划
   - 验证公网入口 `https://newapi.zzzai.cloud:8443`
4. 如需要，把 WSL 验证结果同步回应用摘要文档
5. 视需要处理前端构建警告：
   - circular chunk
   - large chunk warnings

## 8. 关键文件

### 8.1 `new-api`

- `/root/work/new-api/.worktrees/codex-newapi-oplinux-isolation/deploy/op/contract.yaml`
- `/root/work/new-api/.worktrees/codex-newapi-oplinux-isolation/deploy/compute-oplinux-version.sh`
- `/root/work/new-api/.worktrees/codex-newapi-oplinux-isolation/deploy/build-runtime-artifacts.sh`
- `/root/work/new-api/.worktrees/codex-newapi-oplinux-isolation/deploy/package-runtime-image.sh`
- `/root/work/new-api/.worktrees/codex-newapi-oplinux-isolation/deploy/Dockerfile.runtime`
- `/root/work/new-api/.worktrees/codex-newapi-oplinux-isolation/docs/OP_LINUX_DEPLOYMENT.md`
- `/root/work/new-api/.worktrees/codex-newapi-oplinux-isolation/web/.npmrc`
- `/root/work/new-api/.worktrees/codex-newapi-oplinux-isolation/web/pnpm-lock.yaml`

### 8.2 `OP_Linux`

- `/root/work/OP_Linux/.worktrees/codex-newapi-oplinux-isolation/AGENTS.md`
- `/root/work/OP_Linux/.worktrees/codex-newapi-oplinux-isolation/ops/cli/apps.py`
- `/root/work/OP_Linux/.worktrees/codex-newapi-oplinux-isolation/ops/cli/prod0_postgres_app_resource_audit.py`
- `/root/work/OP_Linux/.worktrees/codex-newapi-oplinux-isolation/ops/cli/app_resource_state.py`
- `/root/work/OP_Linux/.worktrees/codex-newapi-oplinux-isolation/infra/compose/newapi/docker-compose.wsl.yml`
- `/root/work/OP_Linux/.worktrees/codex-newapi-oplinux-isolation/inventory/servers/wsl/app-resources.json`
- `/root/work/OP_Linux/.worktrees/codex-newapi-oplinux-isolation/inventory/servers/prod0-main/app-resources.json`
- `/root/work/OP_Linux/.worktrees/codex-newapi-oplinux-isolation/templates/services/newapi.wsl.env.example`
- `/root/work/OP_Linux/.worktrees/codex-newapi-oplinux-isolation/templates/services/newapi.prod0.env.example`

## 9. 新会话建议提示词

可直接在新会话里使用：

```text
继续处理 new-api 接入 OP_Linux 的剩余工作。

资料先看：
- /root/work/OP_Linux/.worktrees/codex-newapi-oplinux-isolation/docs/superpowers/handoffs/2026-03-26-newapi-oplinux-isolation-handoff.md

工作区：
- /root/work/OP_Linux/.worktrees/codex-newapi-oplinux-isolation
- /root/work/new-api/.worktrees/codex-newapi-oplinux-isolation

目标：
- 继续完成 prod0-main 的正式交付准备和验证
- 复用现有 newapi 网站对象
- 保持 PostgreSQL / Redis 隔离模型
- 保持 Node=>pnpm、Python=>uv 规范
```

## 10. 2026-03-26 续做结果

### 10.1 已完成

- `OP_Linux` `ops.cli app` 新增对 `rollback.previous_control_plane.kind=none` 的支持：
  - `deploy --dry-run` 会跳过旧控制面 stop
  - `rollback --dry-run` 会返回“需手工恢复上一镜像”的提示，不再伪造已删除的 1Panel app
- 对应测试已补齐并通过：
  - `uv run python -m pytest tests/test_app_cli.py tests/test_onepanel_app_lifecycle.py tests/test_onepanel_env_targets.py tests/test_cli_entrypoints.py -q`
- `new-api` 合同已改成：
  - `rollback.previous_control_plane.kind=none`
  - `note=当前运行已切到 compose，回退需手工恢复上一镜像`
- 已执行：
  - `app validate-contract`
  - `app deploy --dry-run`
  - `app rollback --dry-run`
  - `app inventory-refresh prod0-main --write`
  - `app doc-sync prod0-main --write`
- 已构建并 ship 新镜像到 `prod0-main`：
  - `newapi-prod:v0.11.9-alpha.2-zzz.20260326.v1.g1c0dd30d576a`
- `prod0-main` 当前 live 容器已运行新镜像，公网验证恢复正常：
  - loopback `/api/status` = `200`
  - public `/api/status` = `200`
  - public `/v1/models` 未授权 = `401`

### 10.2 关键事故与根因

- 在把远端 `/opt/env_ubuntu/secrets/services/newapi.prod0.env` 切到本地隔离版后，`newapi-prod` 立即进入 `Restarting`
- 容器日志根因：
  - PostgreSQL `newapi_prod0` 认证失败
  - `failed SASL auth: FATAL: password authentication failed for user "newapi_prod0"`
- 远端只读核实结果：
  - `postgres18-prod` 中 `newapi_prod0` role 不存在
  - `newapi_prod0` database 不存在
  - 当前仅存在旧库 `newapi`
  - `redis7-prod` 仍是 `requirepass ruoyi123`
  - 还没有 `newapi_prod0` ACL 用户口径

### 10.3 最终 prod0 实际状态

- 应用运行控制面：`/opt/env_ubuntu/infra/compose/newapi/docker-compose.prod0.yml`
- live 镜像：`newapi-prod:v0.11.9-alpha.2-zzz.20260326.v1.g1c0dd30d576a`
- live 网站对象：现有 `newapi`，未新建站点
- 远端运行时 env 已切回隔离口径：
  - PostgreSQL：`newapi_prod0@newapi_prod0`
  - Redis：`newapi_prod0@db2`
- 已在 prod0-main 补齐 tenant 资源：
  - 创建 PostgreSQL role：`newapi_prod0`
  - 创建 PostgreSQL database：`newapi_prod0`
  - 创建 Redis ACL user：`newapi_prod0`
  - 同步远端 tenant secret：
    - `/opt/env_ubuntu/secrets/app-resources/prod0-main/newapi/postgres.env`
    - `/opt/env_ubuntu/secrets/app-resources/prod0-main/newapi/redis.env`
- 已按你的要求直接删除旧 PostgreSQL 库：
  - `newapi` 已 drop，未做数据迁移
- 当前公网验证：
  - loopback `/api/status` = `200`
  - public `/api/status` = `200`
  - public `/v1/models` 未授权 = `401`

### 10.4 当前功能性结论

1. `newapi` 已完成 prod0-main 隔离切换，live runtime 与合同口径一致。
2. 因为旧库 `newapi` 已删除且未迁移数据，当前实例是全新初始化态：
   - `setup=false`
   - 无 root/admin 用户
3. 如果后续要继续投入使用，下一步不是迁移，而是按新库重新初始化业务配置与管理员账号。
