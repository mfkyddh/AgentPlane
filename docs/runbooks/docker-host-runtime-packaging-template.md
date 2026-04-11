# Docker 应用宿主机构建模板

## 1. 目标

这份模板用于新的 Docker 类业务应用接入 `AgentPlane` 时复用统一做法：

1. 在 WSL 宿主机直接构建 runtime artifacts
2. 用 runtime-only Dockerfile 打包正式镜像
3. 继续走 `AgentPlane` 的 `build-artifact -> ship-image -> render-runtime -> plan/apply/verify -> inventory/doc-sync` 链路

这份模板只解决“应用仓库该如何准备构建资产”，不接管正式生产控制面。

active 接入 workflow、交接清单与 `plan/apply/verify/ledger/inventory/doc-sync` 闭环，统一看 [应用项目接入 AgentPlane 工作流](./app-project-delivery-workflow.md)。本文只保留构建模板，不再形成第二控制面。

## 2. 推荐目录结构

应用仓库建议至少包含以下文件：

```text
deploy/
  build-runtime-artifacts.sh
  package-runtime-image.sh
  Dockerfile.runtime
  docker-entrypoint.sh
  op/
    contract.yaml
dist/
  oplinux/
    <app-binary>
    resources/
      ...
```

约定含义：

- `deploy/build-runtime-artifacts.sh`
  在 WSL 宿主机完成前端构建、后端编译、资源收口。
- `deploy/package-runtime-image.sh`
  调用宿主机构建脚本，再执行 `docker build`。
- `deploy/Dockerfile.runtime`
  只封装 `dist/oplinux/` 中的产物，不在 Docker 内重新源码编译。
- `dist/oplinux/`
  作为正式打包的唯一制品目录。

## 3. 宿主机构建脚本模板

最小职责：

1. 安装或复用前端依赖
2. 构建前端产物
3. 下载 Go 或其他后端依赖
4. 编译正式运行时二进制
5. 复制运行时所需资源到 `dist/oplinux/`

最小示例：

```bash
#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
OUTPUT_DIR="${REPO_ROOT}/dist/oplinux"

pnpm --dir "${REPO_ROOT}/frontend" install --frozen-lockfile
pnpm --dir "${REPO_ROOT}/frontend" run build

rm -rf "${OUTPUT_DIR}"
mkdir -p "${OUTPUT_DIR}/resources"

(
  cd "${REPO_ROOT}/backend"
  go mod download
  CGO_ENABLED=0 GOOS=linux go build -o "${OUTPUT_DIR}/app" ./cmd/server
)

cp -R "${REPO_ROOT}/backend/resources/." "${OUTPUT_DIR}/resources/"
```

要求：

- 必须能重复执行
- 必须直接利用宿主机缓存，例如 `pnpm` store、`~/go/pkg/mod`、`~/.cache/go-build`
- 不要把正式 secrets 烘焙进产物

## 4. Runtime Dockerfile 模板

原则：

- 不复制整个源码树
- 不执行 `pnpm install`
- 不执行 `go mod download`
- 不执行 `go build`
- 只复制 `dist/oplinux/` 和必要的 runtime 脚本

最小示例：

```dockerfile
FROM alpine:3.21

RUN apk add --no-cache ca-certificates tzdata curl

WORKDIR /app

COPY dist/oplinux/app /app/app
COPY dist/oplinux/resources /app/resources
COPY deploy/docker-entrypoint.sh /app/docker-entrypoint.sh

RUN chmod +x /app/docker-entrypoint.sh

ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["/app/app"]
```

如果应用依赖 fallback 资源、数据库客户端工具或特定系统库，也在这里显式复制或安装，不要隐式依赖源码目录仍在镜像中存在。

## 5. 打包脚本模板

最小职责：

1. 执行宿主机构建脚本
2. 用 runtime Dockerfile 打包镜像
3. 读取 `IMAGE_NAME` / `IMAGE_TAG`

最小示例：

```bash
#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

IMAGE_NAME="${IMAGE_NAME:-demo-prod}"
IMAGE_TAG="${IMAGE_TAG:-local}"

bash "${SCRIPT_DIR}/build-runtime-artifacts.sh"

docker build \
  -f "${REPO_ROOT}/deploy/Dockerfile.runtime" \
  -t "${IMAGE_NAME}:${IMAGE_TAG}" \
  "${REPO_ROOT}"
```

## 6. 合同模板

Docker 类项目的 `deploy/agentplane/contract.yaml` 推荐写法：

```yaml
schema_version: 1
app_id: demo
artifact:
  build_command: bash deploy/package-runtime-image.sh
  image_name: demo-prod
  image_tag_rule: <upstream>-zzz.<yyyymmdd>.v<n>.g<gitsha>
runtime:
  kind: compose
  container_name: demo-prod
  container_port: 8080
  host_binding: 127.0.0.1:18080
  healthcheck:
    path: /health
    expected_status: 200
  env_template: deploy/prod/demo-prod.env.example
infra:
  depends_on_containers:
    - postgres18-prod
    - redis7-prod
data:
  mounts:
    - host_path: /data/demo/data
      container_path: /app/data
rollback:
  previous_control_plane:
    kind: none
docs:
  app_summary_files:
    prod0-main: docs/AGENTPLANE_DEPLOYMENT.prod0-main.md
    wsl: docs/AGENTPLANE_DEPLOYMENT.wsl.md
inventory:
  service_key: demo
```

重点：

- `artifact.build_command` 应指向脚本，不要直接裸写长串 `docker build`
- `image_name` 与正式容器名建议同族
- 正式镜像 tag 仍由 `IMAGE_TAG` 注入，规则固定为 `<upstream>-zzz.<yyyymmdd>.v<n>.g<gitsha>`
- `agentplane.cli app build-artifact --dry-run` 会尽量给出推荐的 `fork_version`、`delivery_version` 和 `image_tag`
- `agentplane.cli app build-artifact --auto-version` 会按正式规则自动生成 `IMAGE_TAG`

## 7. .dockerignore 模板

如果使用 `dist/oplinux/` 作为唯一制品目录，记得不要把它整体忽略掉。

典型写法：

```gitignore
dist/*
!dist/oplinux/
dist/oplinux/*
!dist/oplinux/app
!dist/oplinux/resources/
dist/oplinux/resources/*
!dist/oplinux/resources/model-pricing/
dist/oplinux/resources/model-pricing/*
!dist/oplinux/resources/model-pricing/model_prices_and_context_window.json
```

实际规则按你的产物结构调整，但原则不变：

- 默认忽略 `dist/`
- 只白名单正式打包所需的 `dist/oplinux/` 内容

## 8. 推荐验证命令

接入前至少跑以下验证：

```bash
bash deploy/build-runtime-artifacts.sh
IMAGE_TAG=test bash deploy/package-runtime-image.sh
docker image inspect <image-name>:test >/dev/null
```

在 `AgentPlane` 中再验证：

```bash
uv run python -m agentplane.cli app build-artifact \
  --contract /root/work/<app>/deploy/agentplane/contract.yaml \
  --repo-root /root/work/AgentPlane \
  --image-tag test \
  --dry-run
```

后续正式交接继续按 active workflow 执行 `deploy --dry-run`、`deploy --execute`、`verify --execute`、`inventory-refresh --write` 与 `doc-sync --write`，不在本文重复维护第二份流程。

## 9. 不要这样做

- 不要把前端依赖安装、前端构建、Go 依赖下载和 Go 编译全部塞进正式 Docker build 主路径
- 不要让 runtime Dockerfile 依赖整个源码树
- 不要把 fallback 资源漏在宿主机构建目录之外
- 不要在应用仓库里复制一套正式生产控制面脚本
