# App Object Aftercare Design

**Date:** 2026-04-02

## Goal

补齐 `app object` 第一版已经承诺但尚未落地的两个对象字段：

- `summary_files`
- `ledger_status`

本轮目标是让 `app object get / verify` 能回答“对象摘要写到哪里了”和“对象台账是否已经落地”，但不把对象核验扩张成现场深度审计。

## Scope

本轮纳入：

- `app object get` 返回 target-aware `summary_files`
- `app object verify` 返回并核验 `ledger_status`
- `app object verify` 对 `summary_files` 做存在性检查
- `app object refresh-ledger` 返回结果补齐 `inventory.object_ledgers.apps` 对齐信息
- 相关测试冻结与最小文档补齐

本轮不纳入：

- ledger 内容与 live state 的逐字段深比对
- `app delivery verify` 范围内的现场容器、探针、入口健康检查
- 新的 app catalog 字段
- 任何应用运行面动作

## Current Gap

当前实现存在两个明显缺口：

1. `get` 固定返回空的 `summary_files`
2. `verify` 没有暴露或核验 `ledger_status`

这与 `app v1` 设计里“对象面至少暴露 `summary_files` 与 `ledger_status`”不一致。

## Decision

采用“中等严格”对象核验：

### `summary_files`

`summary_files` 只回答对象摘要文件路径，不承载内容摘要。

解析规则：

1. 优先读取 contract 的 `docs.app_summary_files.<target>`
2. 若不存在，再回退到 `docs.app_summary_file`
3. 路径统一解析为相对 app repo root 的绝对路径

返回结构：

```json
[
  {
    "target": "prod0-main",
    "path": "/root/work/sub2api/docs/OP_LINUX_DEPLOYMENT.prod0-main.md",
    "source": "docs.app_summary_files",
    "exists": true
  }
]
```

约束：

- 第一版不返回文件内容
- 第一版不猜测额外路径
- 若 contract 未声明摘要路径，则返回空列表

### `ledger_status`

`ledger_status` 只回答对象 ledger 文件和 inventory 指针是否落地，不比较 ledger 内容是否与当前 live state 完全一致。

返回结构：

```json
{
  "json_file": "/root/work/OP_Linux/inventory/servers/prod0-main/ledgers/apps.json",
  "markdown_file": "/root/work/OP_Linux/inventory/servers/prod0-main/ledgers/apps.md",
  "inventory_pointer": "inventory/servers/prod0-main/ledgers/apps.json",
  "json_exists": true,
  "markdown_exists": true,
  "inventory_pointer_ok": true
}
```

检查规则：

1. `inventory/servers/<target>/ledgers/apps.json` 存在
2. `inventory/servers/<target>/ledgers/apps.md` 存在
3. `inventory/servers/<target>/inventory.json.object_ledgers.apps` 指向上述 json ledger 相对路径

第一版不做：

- ledger 中 `items` 与 `search/get` 结果逐字段比对
- ledger markdown 文本内容校验

## Object Surface Changes

### `app object get`

返回结构补强为：

```json
{
  "app": {
    "app": "sub2api",
    "target": "prod0-main",
    "repo_name": "sub2api",
    "service_key": "sub2api",
    "contract_file": "/root/work/sub2api/deploy/op/contract.yaml",
    "control_plane": "compose"
  },
  "inventory_entry": { "...": "..." },
  "summary_files": [
    {
      "target": "prod0-main",
      "path": "/root/work/sub2api/docs/OP_LINUX_DEPLOYMENT.prod0-main.md",
      "source": "docs.app_summary_files",
      "exists": true
    }
  ],
  "ledger_status": {
    "json_exists": true,
    "markdown_exists": true,
    "inventory_pointer_ok": true
  }
}
```

### `app object verify`

在现有 `contract_file`、`inventory_projection` 检查之外，增加：

- `summary_files`
- `ledger_status`

判定规则：

- `summary_files` 只要 contract 声明了路径，就要求这些路径存在
- `ledger_status` 需要三项都为真：`json_exists`、`markdown_exists`、`inventory_pointer_ok`
- 任一项失败，`ok=false`

这样 `verify` 回答的是“对象资料是否完整落地”，不是“应用现在是否运行正常”。

## Refresh-Ledger Semantics

`refresh-ledger` 继续只负责对象 ledger 投影，不回写 contract 或 app summary。

本轮只补两个一致性点：

1. 返回值中显式带上预期 `inventory_pointer`
2. 若 `--write`，确保 `inventory.object_ledgers.apps` 与 ledger json 路径一致

这样 `refresh-ledger` 产物可以直接支撑 `get/verify` 的 `ledger_status` 判断。

## Tests-First Order

1. 先写 `get` 的失败测试，冻结 `summary_files` 与 `ledger_status` 结构
2. 再写 `verify` 的失败测试，冻结：
   - 摘要文件缺失时报错
   - ledger 文件或 inventory 指针缺失时报错
3. 再写 `refresh-ledger` 的失败测试，冻结 `inventory.object_ledgers.apps` 指针写入
4. 然后做最小实现
5. 最后跑 `tests/test_app_object_cli.py` 和最小 CLI 验证

## Success Criteria

- `app object get` 对真实 `sub2api` 返回非空 `summary_files`
- `app object get` 返回 `ledger_status`
- `app object verify` 能把摘要文件缺失与 ledger 指针缺失明确打红
- `app object refresh-ledger --write` 后，`inventory.object_ledgers.apps` 与 `ledgers/apps.json` 对齐
- 不新增 compat / alias / wrapper / 隐式扫描逻辑
