# WSL Host Runtime Packaging Design

**Date:** 2026-03-25

**Status:** Draft approved in conversation, pending written spec review

**Goal**

把 `sub2api` 当前“Docker 内源码编译后再生成镜像”的正式交付路径，调整为“WSL 宿主机预编译产物，再用 runtime Dockerfile 打包镜像”，并把这套做法沉淀为 `OP_Linux` 的标准推荐路径，供后续 Docker 类应用项目复用。

## Background

当前 `sub2api` 的正式合同在 [deploy/op/contract.yaml](/root/work/sub2api/deploy/op/contract.yaml) 中仍然使用：

```yaml
artifact:
  build_command: docker build -f deploy/Dockerfile -t sub2api-prod:${IMAGE_TAG} .
```

这条路径的问题是：

1. 前端依赖安装、前端构建、Go 依赖下载、Go 编译都发生在 Docker build 内。
2. 构建速度依赖 Docker layer cache，无法充分复用 WSL 宿主机已经存在的 `pnpm`、`go mod`、`go build` 本地缓存。
3. 对中国大陆网络环境，Docker build stage 内部的代理、镜像源和包下载链路更脆弱。
4. `OP_Linux` 当前只要求应用仓库提供可复现的 `build_command`，并不要求源码必须在 Docker 内编译，因此可以在不破坏正式交付链路的前提下调整应用仓库的构建实现。

仓库里已经存在更接近目标方案的基础：

- [Dockerfile.goreleaser](/root/work/sub2api/Dockerfile.goreleaser) 已经是“只封装预编译产物”的 runtime image 路线。
- [zqfdocs/wsl-local-rebuild.md](/root/work/sub2api/zqfdocs/wsl-local-rebuild.md) 已记录 WSL 宿主机直接执行前端构建和 Go 编译的现实路径。
- `OP_Linux` 的 [ops/cli/apps.py](/root/work/OP_Linux/.worktrees/codex-host-runtime-packaging/ops/cli/apps.py) `build_artifact()` 当前只是透传合同中的 `artifact.build_command`，这使迁移可以先通过应用仓库脚本完成，而不强制先改控制面 schema。

## Scope

本次工作分为两部分：

1. `sub2api` 样板改造
2. `OP_Linux` 规范固化

本次不做：

- 不把 `OP_Linux` 合同 schema 一次性扩展成新的复杂构建模型。
- 不强制所有现有 Docker 应用同步迁移。
- 不把 `OP_Linux` 改造成负责应用源码编译的统一构建平台。

## Target Workflow

目标工作流分成两个阶段。

### Phase 1: Host Build In WSL

应用仓库在 WSL 宿主机直接完成源码构建：

1. 安装或复用前端依赖
2. 构建前端静态资源
3. 下载 Go 依赖
4. 编译后端二进制
5. 收口 runtime 所需资源文件
6. 生成统一的可打包产物目录

这个阶段必须直接利用宿主机已有缓存：

- `pnpm` store
- `node_modules` / lockfile 驱动的增量安装
- `~/go/pkg/mod`
- `~/.cache/go-build`

### Phase 2: Runtime Image Packaging

Docker 只负责运行时镜像封装：

1. 使用 runtime Dockerfile
2. 复制宿主机构建好的制品目录
3. 复制 entrypoint 和必要的 runtime 资源
4. 生成正式镜像 tag

正式交付链路保持不变：

1. WSL 构建镜像
2. `docker save`
3. `scp`
4. 远端 `docker load`
5. `OP_Linux` 渲染和部署 Compose 运行时

## Architecture

### Application Repository Responsibilities

应用仓库负责：

- 定义如何在 WSL 宿主机预编译产物
- 定义 runtime 打包所需的制品目录结构
- 提供 runtime Dockerfile
- 提供一条稳定的镜像打包脚本作为 `artifact.build_command`

推荐结构：

- `deploy/build-runtime-artifacts.sh`
  负责宿主机前端和后端构建，并生成统一产物目录。
- `deploy/package-runtime-image.sh`
  负责调用产物构建脚本，再执行 `docker build`。
- `deploy/Dockerfile.runtime` 或复用现有 `Dockerfile.goreleaser`
  只封装制品目录，不在 Docker 内源码编译。
- `dist/oplinux/`
  统一存放交付制品，例如：
  - `sub2api`
  - `resources/model-pricing/...`
  - 其他 runtime 必需文件

### OP_Linux Responsibilities

`OP_Linux` 负责：

- 继续把 `artifact.build_command` 作为应用仓库的正式构建入口
- 保持 `build-artifact -> ship-image -> render-runtime -> deploy/verify` 控制链路不变
- 在文档、合同样板和测试中固化“Docker 类项目默认优先 WSL 宿主机预编译，再打 runtime image”的标准推荐路径

第一版仅做轻量固化，不增加复杂 schema。

## Sub2API Concrete Design

### Artifacts Directory

`sub2api` 在仓库内新增统一交付制品目录：

- `dist/oplinux/sub2api`
- `dist/oplinux/resources/model-pricing/model_prices_and_context_window.json`

这套目录必须被 runtime Dockerfile 直接消费。

### Host Build Script

新增宿主机构建脚本，顺序如下：

1. 进入 `frontend/`
2. 执行 `pnpm install --frozen-lockfile`
3. 执行 `pnpm run build`
4. 进入 `backend/`
5. 执行 `go mod download`
6. 执行 `go build -tags embed ...`
7. 清理并重建 `dist/oplinux/`
8. 复制后端二进制和运行时 fallback 资源到制品目录

这条路径直接复用 WSL 本地缓存，而不是依赖 Docker builder cache。

### Runtime Dockerfile

runtime Dockerfile 必须满足：

- 不复制整个源码树
- 不执行 `pnpm install`
- 不执行 `go mod download`
- 不执行 `go build`
- 仅复制 `dist/oplinux/` 产物和 `deploy/docker-entrypoint.sh`
- 保留当前 runtime image 需要的系统包、非 root 用户、健康检查和 fallback 资源布局

现有 [Dockerfile.goreleaser](/root/work/sub2api/Dockerfile.goreleaser) 是最接近的基础，优先在此思路上调整，而不是继续把 [deploy/Dockerfile](/root/work/sub2api/deploy/Dockerfile) 当成正式主路径。

### Packaging Script

新增统一打包脚本：

1. 调用宿主机构建脚本
2. 执行 `docker build -f <runtime-dockerfile> -t sub2api-prod:${IMAGE_TAG} .`

正式合同改为指向该脚本，而不是直接裸写 `docker build`。

## OP_Linux Standardization

第一版在 `OP_Linux` 中固化以下内容。

### Documentation

更新下列文档，明确标准建议路径：

- `docs/architecture/op-linux-app-collaboration.md`
- `docs/runbooks/app-project-delivery-workflow.md`

新增或更新说明：

- Docker 类项目正式推荐路线是“WSL 宿主机预编译 + runtime image 打包”
- 不推荐把前端和后端源码编译都塞进正式 Docker build 主路径
- `artifact.build_command` 应优先指向应用仓库自有打包脚本

### Contract Guidance

保留现有 schema，更新样板示例，把：

```yaml
artifact:
  build_command: docker build ...
```

调整为：

```yaml
artifact:
  build_command: bash deploy/package-runtime-image.sh
```

实际 tag 仍通过 `IMAGE_TAG` 环境变量注入。

### Tests

补充 `OP_Linux` 单元测试，覆盖：

- `build_artifact()` 能继续透传脚本型 `build_command`
- 文档示例和 `sub2api` 样板保持一致

本次不增加新的 schema-level 强校验，避免把第一版通用化做重。

## Migration Strategy

### Step 1

先在 `sub2api` 内引入：

- 宿主机构建脚本
- runtime Dockerfile 主路径
- 打包脚本
- 更新 `deploy/op/contract.yaml`

### Step 2

在 `OP_Linux` 更新文档与测试，让这套样板成为正式推荐路径。

### Step 3

后续新 Docker 项目按相同模式接入：

- 产物收口目录
- 宿主机构建脚本
- runtime Dockerfile
- 包装后的 `artifact.build_command`

这样无需等待复杂 schema 改造，也能立即复制。

## Verification Plan

验收分三层。

### Application-Level Verification

在 `sub2api` 中验证：

1. 宿主机构建脚本能成功生成 `dist/oplinux/`
2. runtime Dockerfile 能成功打包镜像
3. 镜像运行后仍包含：
   - 服务二进制
   - `model-pricing` fallback 资源
   - 当前 entrypoint 行为

### OP_Linux-Level Verification

在 `OP_Linux` 中验证：

1. `uv run python -m pytest tests/test_app_cli.py -q` 中与本改动相关用例通过
2. `ops.cli app build-artifact` 继续能执行新的脚本型 `build_command`

注意：当前 worktree 基线已有 3 个与 `tenant_resources` 相关的既有失败，本次不处理，视为基线噪音。

### Delivery Path Verification

验证以下链路不变：

1. 本地镜像成功生成
2. `docker save` 成功
3. `scp` 成功
4. 远端 `docker load` 成功
5. Compose 运行时仍能按既有 `sub2api-prod` 规则启动

## Risks And Mitigations

### Risk: Host Environment Drift

宿主机构建比 Docker 内全量构建更依赖本机工具链版本。

Mitigation:

- 在应用仓库脚本中固定关键命令和版本前提
- 文档明确 Go / Node / pnpm 版本要求
- 尽量把产物整理过程做成可重复脚本，而不是手工命令

### Risk: Runtime Image Missing Files

切成“预编译产物 + runtime image”后，最容易漏掉 fallback 资源文件。

Mitigation:

- 产物目录显式复制 runtime 必需资源
- 测试和文档继续覆盖 `model-pricing` fallback 资源

### Risk: Over-Generalizing Too Early

第一版若直接改 schema，会扩大改动面。

Mitigation:

- 第一版仅在 `sub2api` 跑通
- `OP_Linux` 只固化推荐实践与样板
- 后续如多个项目都稳定采用，再考虑 schema 升级

## Success Criteria

完成后应满足：

1. `sub2api` 正式镜像构建主路径不再依赖 Docker 内源码编译。
2. `sub2api` 在 WSL 宿主机构建时能复用本机 `pnpm` 和 Go 缓存。
3. `OP_Linux` 仍可通过现有 `build-artifact` / `ship-image` / `render-runtime` 链路完成交付。
4. `OP_Linux` 文档明确该方案是后续 Docker 类项目的推荐标准。
5. 以后新项目可直接参考 `sub2api` 的脚本、目录结构和合同入口复用该模式。
