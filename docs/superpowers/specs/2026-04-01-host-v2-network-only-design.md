# Host V2 Network-Only Migration Design

**Date:** 2026-04-01

## Goal

为 `OP_Linux` 的 `host` 对象域推进第二版正式收口，但本轮只处理 `network`：

- 把受管 Docker bridge 网络治理正式并入 `uv run python -m ops.cli host network ...`
- 删除旧顶层 `uv run python -m ops.cli network ...` 入口
- 不保留 alias、compat wrapper、过渡双入口
- 不把 `onepanel panel`、`onepanel firewall` 并入 `host`
- 不进入应用运行面

## Decision

本轮采用“宿主机对象”和“1Panel 控制面对象”严格分层：

- `host` 只承接宿主机真源动作
- `onepanel` 继续承接 1Panel API 真源对象

因此：

- `network` 进入 `host`
- `panel` 保持在 `onepanel`
- `firewall` 本轮不迁移

## Why `network` Belongs To `host`

`network` 当前治理的是宿主机上的 bridge 网络、bridge 接口、网关地址与路由，而不是 1Panel 页面对象或应用运行时对象。

它的真源来自：

- `inventory/servers/<target>/inventory.json` 中的 `managed_bridge_networks`
- 远端主机上的 `docker network inspect`
- 远端主机上的 `ip addr` / `ip route`

这与 `host inventory`、`host audit`、`host remote bash` 属于同一层宿主机治理面，因此应归入 `host`。

## Why `panel` Stays In `onepanel`

`onepanel panel` 操作的是 1Panel 面板自身设置，不是宿主机通用状态。当前对象真源是 1Panel settings API，例如 `/api/v2/core/settings/search`。

它关注的是：

- 面板设置项
- 面板版本与 bind-domain 之类的控制面状态
- 面板级 plan/apply 变更

这类对象即使运行在某台宿主机上，也不等于“宿主机对象”。若把它并入 `host`，会把对象边界从“宿主机治理”污染成“宿主机 + 1Panel 控制面代理”。

## Scope

本设计覆盖：

- `ops.cli host network audit`
- `ops.cli host network ensure`
- 旧顶层 `network` 入口的移除
- active 文档、AGENTS、skill、测试口径同步到 `host network`

本设计不覆盖：

- `onepanel panel`
- `onepanel firewall`
- `onepanel website`
- 应用部署链路的行为扩展
- `ops/scripts/*` 的新专题脚本增加

## CLI Shape

正式命令面改为：

```bash
uv run python -m ops.cli host network audit <target> --repo-root /root/work/OP_Linux
uv run python -m ops.cli host network ensure <target> --repo-root /root/work/OP_Linux
```

约束：

- `target` 改为位置参数，与现有 `host` 其他动作一致
- 顶层返回结构与 `host` 域保持一致
- 不再暴露顶层 `network` parser

返回结构示例：

```json
{
  "command": "host",
  "action": "network.audit",
  "target": "prod2-main",
  "payload": {
    "ok": true,
    "networks": []
  }
}
```

和：

```json
{
  "command": "host",
  "action": "network.ensure",
  "target": "prod2-main",
  "payload": {
    "ok": true,
    "networks": [],
    "repairs": []
  }
}
```

本轮不再保留 `compat_source` 字段，因为这次不是桥接式引入，而是正式迁移。

## No-Compat Rule

本轮严格执行“无兼容入口”：

- 删除 `ops.cli` 顶层 `network` 子命令
- 不保留 `network` 到 `host network` 的 alias
- active 文档不得再把 `network` 写成正式入口
- skill 不得再把顶层 `network` 作为默认建议命令
- 不新增脚本层 wrapper 充当迁移垫片

如果仓库内还有旧命令示例，只允许出现在 archive/history 或明确标注为历史资料的位置。

## Implementation Strategy

实现采用“测试先行 + 就地收口”：

1. 先新增 `host network` 合同测试，并把 `network` 从 CLI help 期望中移除
2. 再把 `ops/cli/networks.py` 的能力收口进 `ops/cli/host.py`
3. 再从 `ops/cli/app.py` 移除顶层 `network` parser/handler
4. 最后同步文档、skill、AGENTS 与相关合同测试

本轮不重写 `managed_bridge_networks` 的治理算法，重点是对象域迁移与正式入口收口。

## Testing Strategy

测试应覆盖三层：

1. `host` CLI 合同
   - `ops.cli --help` 不再列出顶层 `network`
   - `ops.cli host --help` 列出 `network`
   - `ops.cli host network --help` 列出 `audit` / `ensure`
   - `host network audit|ensure` 的顶层 `command/action/target`
2. 既有网络治理行为
   - 原 `network` 的 audit/ensure 行为测试迁到 `host` 命令形状
   - 不降低 live state 校验和 repair 顺序约束
3. 文档合同
   - active 文档与 skill 默认入口改成 `host network`
   - active 文档不再把顶层 `network` 当正式入口

## Files To Change

- `ops/cli/app.py`
- `ops/cli/host.py`
- `ops/cli/networks.py`
- `tests/test_cli_entrypoints.py`
- `tests/test_host_cli.py`
- `tests/test_app_cli.py`
- `tests/test_docs_no_legacy_terms.py`
- `README.md`
- `AGENTS.md`
- `docs/architecture/control-plane.md`
- `docs/runbooks/wsl-host-governance.md`
- `docs/runbooks/app-project-delivery-workflow.md`
- `.codex/skills/host-ops/SKILL.md`

## Risks

### Risk 1: `host` 语义被继续做大

如果顺手把 `panel` 或 `firewall` 一起吞进来，本轮范围会失控，且会再次混淆宿主机对象与 1Panel 控制面对象。

控制方式：

- 本轮只迁移 `network`
- 其余对象域继续留在原域，后续单独设计

### Risk 2: 只改命令名，不改正式口径

如果代码迁了，但文档和 tests 仍承认顶层 `network`，仓库会继续保留双真源。

控制方式：

- 代码、文档、skill、测试同轮收口
- active 资产不再承认顶层 `network`

### Risk 3: 为了迁移再长出脚本层

如果新增 shell/python wrapper 去转发旧入口，会违背本轮“无 compat、无脚本正式面”的约束。

控制方式：

- 不新增 wrapper
- 正式入口只保留 `ops.cli host network ...`

## Success Criteria

当以下条件同时成立时，本轮视为完成：

- `ops.cli` 顶层不再存在 `network`
- `host network audit|ensure` 可用
- 原网络治理测试迁移后仍通过
- active 文档和 skill 默认入口统一为 `host network`
- `onepanel panel` 仍保留在 `onepanel`，没有被错误并入 `host`
