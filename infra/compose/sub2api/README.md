# Sub2API

- 这是 AgentPlane 受管的应用层 Compose 资产，不是基础数据服务模板。
- WSL 模板：`docker-compose.wsl.yml`
- 生产模板：`docker-compose.prod0.yml`、`docker-compose.prod2.yml`
- 生产容器名固定为 `sub2api-prod`，依赖容器固定为 `postgres18-prod` 与 `redis7-prod`
- 生产容器接入 `zqf_network`，通过容器名通信；容器名变更必须先同步合同、inventory、Compose 与验证用例
- 生产入口固定绑定 `127.0.0.1:18080:8080`，再由 1Panel 网站对象 `token` 与 OpenResty 对外暴露
