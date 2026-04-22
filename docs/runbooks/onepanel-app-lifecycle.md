# 1Panel 应用生命周期手册

## 定位

本手册保留为边界说明与兼容排障文档，不再把 `onepanel app/project` 视为公开默认入口。

- 从源码交付的应用 catalog object 走 `uv run python -m agentplane.cli app object ...`
- 从源码交付的应用合同、构建、部署、回滚走 `uv run python -m agentplane.cli app delivery ...`
- 运行态 restart / reconcile / verify 走 `uv run python -m agentplane.cli service ...`
- 公网入口发布走 `uv run python -m agentplane.cli website publish ...`
- fixture / verification / ledger 走 `uv run python -m agentplane.cli projection ...`
- `onepanel` 公开面只剩 provider/debug 对象：`panel`、`firewall`、`cronjob`、`task`

`api_request.py` 与内部 object API 继续保留为 provider/debug substrate；旧 `app_lifecycle.py` / `project_lifecycle.py` 脚本入口已退役。
Formal catalog apps with `schema_version: 2` must use `uv run python -m agentplane.cli app object ...`, `app delivery ...`, `service ...`, and `website ...`; these compat helpers are not the active execution path.

## 当前边界

| 需求 | 正式入口 | 说明 |
| --- | --- | --- |
| 应用 catalog 核验 | `uv run python -m agentplane.cli app object search --target prod0-main --repo-root <repo-root>` | 只接受 catalog 中已登记 app；当前 active catalog 为空。 |
| 应用交付合同校验 | `uv run python -m agentplane.cli app delivery validate-contract --target <target> --app <app> --repo-root <repo-root>` | 只适用于重新 onboard 的源码交付应用。 |
| 运行态服务核验 | `uv run python -m agentplane.cli service verify --target prod0-main --name sub2api --repo-root <repo-root>` | formal service 只接受 inventory 中已声明的受管运行服务对象。 |
| 运行态服务操作 | `uv run python -m agentplane.cli service plan --target prod0-main --name legacy_runtime --operation restart --repo-root <repo-root>` | 1Panel-backed runtime 也通过 `service` 暴露稳定操作。 |
| 公网入口发布 | `uv run python -m agentplane.cli website publish plan --target prod0-main --config-file <config-file> --cloudflare-env-file <cloudflare-env-file> --repo-root <repo-root>` | `website publish` 是 Cloudflare + 1Panel 公网入口的正式任务入口。 |
| 验证与台账 | `uv run python -m agentplane.cli projection verification run --target prod0-main --profile prod0-readonly --repo-root <repo-root>` | `projection` 负责 verification / fixture / ledger。 |

## 运行态操作示例

inventory 中声明为 `onepanel-app` 或 `onepanel-compose` 的 tracked runtime service，一律通过 `service` 访问：

```bash
uv run python -m agentplane.cli service get --target prod0-main --name legacy_runtime --repo-root <repo-root>
uv run python -m agentplane.cli service plan --target prod0-main --name legacy_runtime --operation restart --repo-root <repo-root>
uv run python -m agentplane.cli service apply --target prod0-main --name legacy_runtime --operation restart --repo-root <repo-root> --execute

uv run python -m agentplane.cli service get --target prod0-main --name legacy_project --repo-root <repo-root>
uv run python -m agentplane.cli service plan --target prod0-main --name legacy_project --operation restart --repo-root <repo-root>
uv run python -m agentplane.cli service apply --target prod0-main --name legacy_project --operation restart --repo-root <repo-root> --execute
```

如果目标服务是 `compose` 控制面，`service` 才会额外开放 `reconcile`：

```bash
uv run python -m agentplane.cli service plan --target prod0-main --name sub2api --operation reconcile --repo-root <repo-root>
uv run python -m agentplane.cli service apply --target prod0-main --name sub2api --operation reconcile --repo-root <repo-root> --execute
```

## 验证与回写

运行态变更完成后，至少做两步：

```bash
uv run python -m agentplane.cli service verify --target prod0-main --name sub2api --repo-root <repo-root>
uv run python -m agentplane.cli projection ledger refresh --target prod0-main --repo-root <repo-root> --write
```

只读兼容性验证继续走：

```bash
uv run python -m agentplane.cli projection verification run --target prod2-main --profile prod2-readonly --repo-root <repo-root> --write-report
```

## Compat / Troubleshooting

- 低层 provider helper：`agentplane/scripts/onepanel/api_request.py`
- 1Panel app / compose lifecycle：通过 formal CLI 与内部 object API 计划执行，不再保留脚本入口
- 这些 substrate 不是公开默认命令面，不在 docs / skill 中作为首选入口暴露
- 历史收敛材料、切换窗口记录、一次性现场补救，应转存到 `docs/archive/runbooks/...`
