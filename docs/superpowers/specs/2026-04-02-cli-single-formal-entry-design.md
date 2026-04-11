# CLI Single Formal Entry Design

**Date:** 2026-04-02

**Status:** Draft approved in conversation, pending written spec review

## Goal

把 `OP_Linux` 的 CLI 正式入口收敛成唯一一套公开命令面，不再保留 `inventory / audit / remote / secrets` 顶层入口，也不再保留“compat / legacy still supported”的迁就语义。

本轮完成后，宿主机基础治理只能通过 `uv run python -m ops.cli host ...` 进入；README、runbook、skills、帮助输出和测试口径全部同步改成这一事实。

## Background

当前 `master` 已经完成了 `host / service / website / tenant / app / projection` 这批对象域的第一版公开命令面，但仓库仍同时暴露旧顶层入口：

- `inventory`
- `audit filesystem`
- `remote bash`
- `secrets ...`

这造成三个持续问题：

1. `ops.cli --help` 仍像双控制面，旧入口和对象域入口并列暴露。
2. active 文档、部分 skills 和测试仍需要专门说明“host 是正式入口，但旧命令也还能用”，让 CLI-first 口径一直带着历史包袱。
3. `host` 的若干返回结构仍带 `compat_source`，等于公开承认自己还只是旧命令的桥接层，而不是真正的正式命令面。

因此，这一轮不是继续扩新对象域，而是把已经立起来的新命令面彻底扶正。

## Scope

本轮只覆盖以下收口动作：

1. 删除顶层旧入口 `inventory / audit / remote / secrets`。
2. 把宿主机基础治理正式入口彻底收敛到 `host`。
3. 重整 `host` 下的 secrets 子命令形状，避免顶层 `secrets` 删除后出现能力悬空。
4. 删除 active 文档、skills、帮助输出、测试中的旧入口口径。
5. 删除 `host` 返回结构中的 `compat_source` 等过渡字段。

本轮不做：

1. 不删除 `cleanup / automation / onepanel` 这类尚未完成对象化收口的任务域。
2. 不重写 `ops/cli/inventory.py`、`ops/cli/audit.py`、`ops/cli/remote.py`、`ops/cli/secrets.py` 的底层实现逻辑，只改变公开入口和返回合同。
3. 不改 `service / website / tenant / app / projection` 的对象边界。
4. 不提供旧入口报错提示、别名或自动迁移提示。

## Decision

采用“单正式入口硬删除”方案，而不是隐藏旧入口或保留兼容报错。

### Rejected Option A: 只从帮助和文档里隐藏旧入口

不采用。代码里还保留可执行入口，本质上仍是双入口，只是换成“不明显的双入口”。

### Rejected Option B: 旧入口保留，但执行时报错提示新命令

不采用。只要 parser 仍接受旧命令，它就仍然是兼容层，不符合“不进行兼容”的要求。

### Chosen Option: 硬删除旧入口，只保留正式对象入口

采用以下原则：

1. parser 不再注册 `inventory / audit / remote / secrets` 顶层命令。
2. 主 dispatch 不再处理这些顶层命令。
3. active 文档、skills、帮助输出不再出现这些命令作为可用入口。
4. `host` 返回结构不再带 `compat_source`。
5. 用户执行旧命令时，直接由 argparse 视为未知命令，不提供 compatibility fallback。

## Target State

本轮完成后，公开命令面收敛为：

### 保留的正式入口

- `uv run python -m ops.cli host ...`
- `uv run python -m ops.cli service ...`
- `uv run python -m ops.cli website ...`
- 已移除的旧资源对象入口
- `uv run python -m ops.cli app ...`
- `uv run python -m ops.cli projection ...`

### 暂时保留的任务域

- `uv run python -m ops.cli cleanup ...`
- `uv run python -m ops.cli automation ...`
- `uv run python -m ops.cli onepanel ...`

### 删除的旧入口

- `uv run python -m ops.cli inventory ...`
- `uv run python -m ops.cli audit filesystem ...`
- `uv run python -m ops.cli remote bash ...`
- `uv run python -m ops.cli secrets ...`

## Host CLI Shape

删除旧顶层入口后，宿主机基础治理统一进入 `host`。

### Host commands after cutover

```bash
uv run python -m ops.cli host inventory <target> [--repo-root ...] [--write]
uv run python -m ops.cli host audit <target> [--repo-root ...]
uv run python -m ops.cli host network audit <target> [--repo-root ...]
uv run python -m ops.cli host network ensure <target> [--repo-root ...]
uv run python -m ops.cli host remote bash <target> [--repo-root ...] [--script-file ...] [--dry-run] [-- <arg>...]
uv run python -m ops.cli host secrets init-data-services <target> [--repo-root ...] [--force]
uv run python -m ops.cli host secrets sync-layout <target> [--repo-root ...] [--write]
```

### Secrets reshaping

本轮必须把 `host` 下的 secrets 从单个扁平动作提升成子命令族，否则删除顶层 `secrets` 后会丢失 `init-data-services` 能力。

新的正式形状：

- `host secrets init-data-services`
- `host secrets sync-layout`

旧的 `host secrets-layout` 同步删除，不保留 alias。

## Output Contract

`host` 对象面不再公开“我是从旧入口桥接过来”的过渡字段。

### Required top-level shape

```json
{
  "command": "host",
  "action": "inventory",
  "target": "wsl",
  "payload": {}
}
```

约束如下：

1. 顶层只保留 `command / action / target / payload` 这组正式字段。
2. 删除 `compat_source`。
3. `host network.*`、`host remote.bash`、`host secrets.*` 与 `host inventory / audit` 统一采用同一顶层结构。
4. 底层 helper 暂时仍可返回旧内部 payload，但对外由 `host` 包装成正式对象合同。

## File-Level Design

### `ops/cli/app.py`

需要完成两件事：

1. 不再注册 `inventory / audit / remote / secrets` 顶层 parser。
2. 不再 dispatch 这四类顶层命令。

同时保留：

- `cleanup`
- `automation`
- `onepanel`
- `host`
- `service`
- `website`
- `tenant`
- `app`
- `projection`

### `ops/cli/host.py`

`host` 成为宿主机基础治理唯一公开入口。本轮需要：

1. 保留 `inventory / audit / network / remote`。
2. 把 `secrets-layout` 改成 `secrets` 子命令族。
3. 删掉所有 `compat_source`。
4. 统一 `host` 全域顶层输出结构。

### `ops/cli/inventory.py`

保留底层函数，例如 `generate_inventory_snapshot()`，但它不再承担顶层公开命令身份。

若现有返回 payload 中带有明显的旧命令名，应把旧命令名沉到 helper 内部或由 `host` 包装后对外隐藏。

### `ops/cli/audit.py`

保留宿主机审计底层逻辑，但不再公开顶层 `audit filesystem` 命令面。

### `ops/cli/remote.py`

保留远端执行 substrate 和 `execute_remote_bash()` 这类内部 API，供 `host remote bash` 复用；顶层 `remote` parser 删除。

### `ops/cli/secrets.py`

保留 secrets 底层函数，但不再公开顶层 `secrets` parser。

本轮需要把现有能力映射到 `host secrets`：

- `init_data_services()` -> `host secrets init-data-services`
- `materialize_legacy_host_layout()` -> `host secrets sync-layout`

同时需要清理返回结构中的顶层 `command=secrets`、`action=sync-host-layout` 这类旧公开语义，避免它们继续泄露到正式对象合同。

## Documentation Changes

### Active docs

以下 active 资产必须改成只写新正式入口：

- `README.md`
- `AGENTS.md`
- `docs/runbooks/bootstrap-secrets.md`
- `docs/runbooks/control-plane-domain-onboarding.md`
- `docs/runbooks/wsl-host-governance.md`
- `docs/runbooks/powershell-wsl-remote-bash.md`
- `docs/runbooks/prod0-main-governance.md`
- `.codex/skills/host-ops/SKILL.md`
- `.codex/skills/app-resource-ops/SKILL.md`

### Historical docs

历史 spec、plan、handoff、archive 可以保留旧命令，因为它们本来就是历史记录；本轮不要求批量回写历史资产。

但 active 文档不得再出现“旧入口也还能用”的口径。

### Legacy migration doc

`docs/runbooks/control-plane-legacy-migration.md` 不能再把旧入口当作当前仍可执行的 compatibility path。它需要改成纯历史迁移说明，或者移出 active runbook 角色。

## Testing

### CLI tests

需要更新：

- `tests/test_cli_entrypoints.py`
- `tests/test_host_cli.py`
- `tests/test_secrets_cli.py`

关键验证：

1. `ops.cli --help` 不再出现 `inventory / audit / remote / secrets`。
2. `host --help` 暴露 `inventory / audit / network / remote / secrets`。
3. `host secrets --help` 暴露 `init-data-services / sync-layout`。
4. `host inventory / audit / remote / secrets.*` 的顶层输出都不再带 `compat_source`。
5. 旧命令执行时返回 argparse 未知命令错误。

### Docs tests

`tests/test_docs_no_legacy_terms.py` 需要从“旧入口允许存在但要标 compat”改为：

1. active 文档只允许新正式入口。
2. active 文档不再出现 `ops.cli inventory / audit filesystem / remote bash / secrets` 作为可执行命令。

## Risks

### 风险 1：删入口后，`host` 下 secrets 形状不完整

如果只删顶层 `secrets`，不补 `host secrets init-data-services`，会直接丢失现有正式操作能力。

控制方式：本轮把 `host secrets` 子命令族一起落地。

### 风险 2：只删 parser，不删文档和测试

这样会出现“代码已经不支持，但文档和 skills 仍在教旧命令”的硬断层。

控制方式：CLI、README、runbook、skills、测试同一轮一起收口。

### 风险 3：表面删除入口，返回合同仍保留 compat 痕迹

如果 `host` 仍返回 `compat_source`，那公开对象面仍然没真正扶正。

控制方式：删除 `compat_source`，统一 `host` 顶层合同。

## Success Criteria

满足以下条件，才算这轮完成：

1. `uv run python -m ops.cli --help` 不再出现 `inventory / audit / remote / secrets`。
2. 宿主机基础治理只能通过 `host` 进入。
3. `host secrets` 成为唯一 secrets 正式入口。
4. active 文档、skills、帮助输出不再引用旧入口作为可用命令。
5. `host` 顶层返回结构不再出现 `compat_source`。
6. 旧顶层入口执行时不再被 parser 接受。
