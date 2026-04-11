# ChatGPT Register V2

- Tracked templates live here: `docker-compose.wsl.yml` and `docker-compose.prod0.yml`.
- The prod2 parallel runtime lives in `../chatgpt-register-v2-prod2/docker-compose.prod2.yml`.
- Real runtime values live in `secrets/services/chatgpt-register-v2.wsl.env`, `secrets/services/chatgpt-register-v2.prod0.env`, and `secrets/services/chatgpt-register-v2-prod2.prod2.env`.
- The tracked examples are `templates/services/chatgpt-register-v2.env.example` and `templates/services/chatgpt-register-v2-prod2.prod2.env.example`.
- Runtime data lives under `/data/chatgpt-register-v2/data` for prod0/wsl and `/data/chatgpt-register-v2-prod2/data` for prod2.

说明：

- 该应用属于 internal worker，不对公网暴露业务入口。
- `wsl` 与 `prod0` 都通过 `CHATGPT_REGISTER_CONFIG_HOST_PATH -> CHATGPT_REGISTER_CONFIG_PATH` 显式挂载外部完整 config JSON；正式 secrets 不再烘进镜像。
- `wsl` 应使用独立的 `chatgpt-register-v2.wsl.config.json`，其中需要把健康检查和 `sub2api-wsl` 的基址固化为 WSL 受管运行面可用的值。
- prod0 / WSL 统一使用 `chatgpt-register-v2` 目录，不再保留 legacy `chatgpt-register-wsl` 控制面。
- prod2 由镜像默认入口固定到 `prod2 + sub2api-local`。
- prod2 默认参数为 `workers=5`、`interval=3`、`mail-wait=300`，需要临时调参时再通过 compose `command` 覆盖。
- WSL 健康探针对外绑定 `0.0.0.0:18081`；prod0 对外只绑定 `127.0.0.1:18081`。
- prod2 固定通过本机 `sub2api-prod:8080` 导入，健康探针绑定 `127.0.0.1:18082`，且不下发代理。
