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

<!-- BEGIN AGENTPLANE_ONEPANEL_LEDGER -->
## 1Panel 对象台帐投影

- 生成时间：`2026-04-22T11:00:06.349457+00:00`
- 刷新命令：`uv run python -m agentplane.cli projection ledger refresh --target wsl --repo-root <repo-root> --write`

### 对象计数

- `websites`: 0
- `containers`: 3
- `firewall`: 0
- `cronjobs`: 2
- `apps`: 0
- `app_resources`: 1
- `automations`: 2

### 最近 CLI 动作

- 无最近 onepanel CLI 记录。
<!-- END AGENTPLANE_ONEPANEL_LEDGER -->
