# wsl 摘要

## 身份

- 备注：`WSL 跳板机`

## 应用控制面

- `sub2api`：`compose` / `sub2api-dev` / `http://127.0.0.1:18080`
- 依赖容器：`postgres18-dev, redis7-dev`
- app_resource_summary.postgres：`{"database": "sub2api_wsl", "secret_file": "secrets/hosts/wsl/apps/sub2api/resources/postgres.env", "user": "sub2api_wsl"}`
- app_resource_summary.redis：`{"db": 1, "key_prefix": "sub2api:wsl:", "secret_file": "secrets/hosts/wsl/apps/sub2api/resources/redis.env"}`

## 资料入口

- 结构化清单：`inventory/servers/wsl/inventory.json`
- 机器真源：`inventory/servers/wsl/inventory.json`
- 本摘要：`inventory/servers/wsl/README.md`
- README 只保留非敏感摘要，不承载第二真源；脚本消费和对象细节以 JSON 为准。
