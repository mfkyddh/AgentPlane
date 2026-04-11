# WSL Governance Convergence Design

## Goal

收口当前 WSL 的仓库治理边界，让仓库声明、审计规则、inventory 快照和实际运行态重新一致。

## Scope

- 让 `minio-dev`、`postgres18-dev`、`redis7-dev` 从当前仓库根重新受管。
- 把 `chatgpt-register-v2-wsl` 以 `chatgpt-register-wsl` 服务目录正式纳入 `infra/compose/`。
- 把 `cliproxyapi` 的环境文件从 `infra/compose/cliproxyapi/` 迁到 `secrets/services/`，并更新模板和审计规则。
- 更新 WSL inventory 生成与落盘内容。
- 清理已确认不再需要的 WSL 本地 legacy 目录与数据目录。

## Non-Goals

- 不改动外部业务仓库源码。
- 不处理生产机 `prod0-main` 的运行态。
- 不改变 `chatgpt-register-v2` 业务逻辑，只治理其在 WSL 的部署编排。

## Design

### Compose Governance

所有受管服务都必须在 `infra/compose/<service>/` 下同时拥有 `docker-compose.wsl.yml` 与 `docker-compose.prod0.yml`。空壳目录 `token-openresty` 不再保留，避免审计误判为缺模板的受管服务。

新建 `infra/compose/chatgpt-register-wsl/`，让当前运行中的 `chatgpt-register-v2-wsl` 改由本仓库的 compose 资产声明。WSL 模板继续使用当前本地镜像与 host 网络；prod0 模板仅提供合规占位编排，不改变现有生产部署事实。

### Secret And Env Layout

`cliproxyapi` 的 `.env.wsl` 和 `.env.prod0` 从 compose 目录迁到 `secrets/services/cliproxyapi.wsl.env` 与 `secrets/services/cliproxyapi.prod0.env`，模板说明同步改为指向 `templates/services/cliproxyapi.env.example`。审计规则新增对 `infra/compose/<service>/.env.*` 的检查，避免把运行时 env 混放到 tracked compose 目录里。

`chatgpt-register-wsl` 采用同样口径，在 `secrets/services/` 放环境文件，在 `templates/services/` 放示例文件。

### Inventory

WSL inventory 继续展示运行中容器，但明确拆分为：

- `docker_containers`: 由当前仓库声明的受管容器。
- `unmanaged_docker_containers`: 当前 WSL 上运行但不属于本仓库声明的容器。

这样既保留现场信息，又避免治理视图被外部项目污染。更新后的 inventory 还会反映新的仓库根、受管服务列表和纳入治理后的 `chatgpt-register-wsl`。

### Runtime Cleanup

完成编排切换后，重新用当前仓库根拉起 `minio-dev`、`postgres18-dev`、`redis7-dev` 和 `chatgpt-register-v2-wsl`。随后清理 `/data/apps/nginx-ui-official` 与 `/data/nginx/sites/*`，因为这两处在当前 WSL 上已无对应受管容器，且已被用户明确指定删除。

## Verification

- 审计：`uv run python -m ops.cli audit filesystem --env wsl --repo-root /root/work/OP_Linux`
- Inventory：`uv run python -m ops.cli inventory wsl --repo-root /root/work/OP_Linux`
- 测试：`PYTHONPATH=/root/work/OP_Linux uv run pytest tests/test_wsl_audit.py tests/test_inventory_generation.py tests/test_cli_entrypoints.py -q`
- 运行态：`docker inspect` 确认相关容器的 compose label 指向当前仓库根。
