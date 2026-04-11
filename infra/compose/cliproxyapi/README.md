# CLIProxyAPI

仓库里只保留可提交的 compose 资产和模板。

- WSL 模板：`infra/compose/cliproxyapi/docker-compose.wsl.yml`
- 0号生产机模板：`infra/compose/cliproxyapi/docker-compose.prod0.yml`
- WSL 部署参数：`secrets/services/cliproxyapi.wsl.env`
- 0号生产机部署参数：`secrets/services/cliproxyapi.prod0.env`
- live config：`/data/cliproxyapi/config/config.yaml`
- 模板文件：`templates/services/cliproxyapi.config.yaml.example`
- env 模板：`templates/services/cliproxyapi.env.example`
- 持久化数据：`/data/cliproxyapi/{auths,logs,static}`
- 当前模板统一通过 `0.0.0.0:8318` 发布 API；本机访问示例仍可使用 `http://127.0.0.1:8318/v1`

说明：

- 旧的 `/root/cliproxyapi` 二进制部署已移除，`8317` 当前不再由 CLIProxyAPI 占用；仓库管理的 Docker 实例统一使用 `8318`。
- CLIProxyAPI `v6.9.10` 的管理页和 API 共享同一个 HTTP 监听口；历史上的 `8085` 不再作为仓库管理实例的有效入口。
- WSL 推荐启动命令：
  `docker compose --env-file /root/work/AgentPlane/secrets/services/cliproxyapi.wsl.env -f /root/work/AgentPlane/infra/compose/cliproxyapi/docker-compose.wsl.yml up -d`
- 0号生产机推荐启动命令：
  `docker compose --env-file /root/work/AgentPlane/secrets/services/cliproxyapi.prod0.env -f /root/work/AgentPlane/infra/compose/cliproxyapi/docker-compose.prod0.yml up -d`
