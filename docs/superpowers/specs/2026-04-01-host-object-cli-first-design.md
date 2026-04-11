# Host Object CLI-First Design

## 结论

本设计把 `host` 引入为 `OP_Linux` 控制面的第一版显式对象域。第一版只上收宿主机基础治理入口，不重写底层实现，不进入应用运行面，也不在本轮吞并 `network`、`onepanel panel`、`onepanel firewall`。

正式目标是让宿主机治理的默认命令面从分散的 `inventory`、`audit filesystem`、`remote bash`、`secrets` 子路径，收口到统一的 `uv run python -m ops.cli host ...`。

## 范围

本轮只覆盖以下宿主机基础能力：

- `host inventory <target>`
- `host audit <target>`
- `host remote bash <target> ...`
- `host secrets-layout <target>`

本轮明确不做：

- 不重写 `inventory`、`audit filesystem`、`remote bash`、`secrets` 的现有底层实现
- 不把 `network` 对象域直接并入 `host`
- 不把 `onepanel panel`、`onepanel firewall` 直接并入 `host`
- 不进入应用层运行面

## 背景与问题

当前仓库已经把正式入口大体收口到 `ops.cli`，但宿主机治理能力仍分散在多个顶层命令和专题域里：

- `inventory <target>`
- `audit filesystem --env <target>`
- `remote bash <target>`
- `secrets ...`
- `network ...`
- `onepanel panel ...`
- `onepanel firewall ...`

这带来两个问题：

1. skill、runbook、architecture 已经把这批能力视为 `host` 域的一部分，但 CLI 还没有显式 `host` 对象面。
2. 宿主机基础治理与网络、1Panel 面板对象、1Panel 防火墙对象仍混在不同动作域中，不利于下一轮继续扩到 `service / website / tenant`。

因此第一版 `host` 的目标不是“一次性吞完所有宿主机相关能力”，而是先把宿主机基础治理的正式对象入口立起来。

## 对象边界

### 第一版纳入 `host` 的对象动作

#### `host inventory`

宿主机结构化清单入口。面向 `inventory/servers/<target>/inventory.json` 及其生成逻辑，负责表达宿主机的结构化快照。

第一版桥接现有 `inventory <target>`。

#### `host audit`

宿主机基线审计入口。第一版只承接当前 `audit filesystem --env <target>` 的治理合同，不在本轮扩展新的 host doctor 模型。

#### `host remote bash`

宿主机远端执行入口。第一版保持现有远端 Bash 语义与 transport substrate，不改变 SSH 解析、ledger 写入和 dry-run 逻辑。

#### `host secrets-layout`

宿主机 secrets 布局合同入口。第一版只统一“宿主机 secrets / host-first layout”的调用面，内部桥接现有 `secrets` 子命令，不创造第二套 secrets 实现。

### 第一版明确不纳入 `host` 的对象动作

#### `network`

`network` 继续作为独立域存在。原因是它已经带有明显的基础设施对象语义和远端修复动作，直接吞并到 `host` 会把宿主机基础治理与 bridge network 对象化混在一起。

本轮只允许在 `host` 文档中把它标注为“下一阶段桥接对象”，不做行为迁移。

#### `onepanel panel`

`panel` 继续保留在 `onepanel` 域。它属于 1Panel 控制面对象，而不是宿主机基础治理的最小闭环。

#### `onepanel firewall`

`firewall` 虽然属于 host 相关治理，但当前实现和 skill 已经绑定到 `onepanel` 对象面。第一版不做对象迁移，只在 `host` 架构中标注它是后续桥接候选。

## CLI 设计

### 命令形状

第一版 `host` 命令面：

```bash
uv run python -m ops.cli host inventory <target> [--repo-root ...] [--write]
uv run python -m ops.cli host audit <target> [--repo-root ...]
uv run python -m ops.cli host remote bash <target> [--repo-root ...] [--script-file ...] [--dry-run] [-- ...]
uv run python -m ops.cli host secrets-layout <target> [--repo-root ...] [--write]
```

### 子命令映射

| `host` 子命令 | 第一版内部桥接 | 说明 |
|---|---|---|
| `host inventory <target>` | `inventory <target>` | 沿用现有 inventory 生成与写回逻辑 |
| `host audit <target>` | `audit filesystem --env <target>` | 先冻结现有宿主机基线审计语义 |
| `host remote bash <target>` | `remote bash <target>` | 只改变对象入口，不改变 transport substrate |
| `host secrets-layout <target>` | 现有 `secrets` 子命令 | 统一宿主机 layout 调用面 |

### 返回结构

第一版保持“对象入口统一，底层 payload 尽量不变”：

```json
{
  "command": "host",
  "action": "inventory",
  "target": "wsl",
  "compat_source": "inventory",
  "payload": {
    "...": "bridge existing payload"
  }
}
```

约束如下：

- 顶层统一为 `command=host`
- `action` 使用宿主机对象动作名，如 `inventory`、`audit`、`remote.bash`、`secrets-layout`
- `target` 始终显式保留
- `payload` 尽量保留现有桥接子系统的原始结构
- 第一版新增 `compat_source`，明确当前仍是桥接实现，不伪装成全新底层

### 兼容策略

本轮不删除旧入口：

- `inventory`
- `audit filesystem`
- `remote bash`
- 现有 `secrets` 子命令

兼容策略为：

1. `host` 成为新的正式对象入口。
2. active 文档、skill、architecture 优先指向 `host`。
3. 旧入口继续可用，作为 compat / legacy stable path 保留。
4. 本轮不做破坏性迁移，不强行把旧入口标成错误。

## 测试设计

### 新增测试

新增 `tests/test_host_cli.py`，冻结第一版 `host` 合同：

- `ops.cli --help` 中存在 `host`
- `ops.cli host --help` 暴露预期子命令
- `host inventory` 的顶层 `command/action/target/compat_source`
- `host audit` 的顶层 `command/action/target/compat_source`
- `host remote bash --dry-run` 的桥接结构
- `host secrets-layout` 的顶层合同

### 继续保留的旧测试

现有 legacy/compat 入口测试继续保留，证明：

- `inventory`
- `audit filesystem`
- `remote bash`
- `secrets`

在第一版 `host` 引入后仍然可用。

### 本轮不新增的测试

本轮不测试以下行为迁移：

- `network` 被 `host` 吸收
- `onepanel panel` 被 `host` 吸收
- `onepanel firewall` 被 `host` 吸收

因为这些都不属于第一版范围。

## 文档与 Skill 调整

本轮需要同步的资产：

- `README.md`
- `docs/architecture/control-plane.md`
- `docs/runbooks/wsl-host-governance.md`
- `.codex/skills/host-ops/SKILL.md`
- 必要的文档合同测试

调整原则：

1. 宿主机治理的默认入口改写为 `uv run python -m ops.cli host ...`
2. 旧入口如果仍需保留，只标成 compat/helper/stable path
3. `network`、`panel`、`firewall` 在文档里明确列为下一阶段桥接对象，不误写成已完成迁移

## 实施顺序

实现顺序固定如下：

1. 先新增 `host` 设计 spec
2. 再写对应 implementation plan
3. 再按 TDD 实现 `host` CLI 合同与文档桥接
4. 本轮不进入 `network / panel / firewall` 对象化迁移

## 风险与控制

### 风险 1：重复入口继续膨胀

如果 `host` 只是再包一层而不调整文档与测试，仓库会出现“新入口 + 旧入口都自称正式”的问题。

控制方式：文档、skill、测试同时切到 `host` 正式口径；旧入口只保留 compat 语义。

### 风险 2：第一版范围过宽

如果本轮同时吞并 `network`、`panel`、`firewall`，实现、测试和文档写集会明显放大，也会模糊宿主机基础治理和 1Panel 对象面之间的边界。

控制方式：第一版严格限制在 `inventory / audit / remote / secrets-layout`。

### 风险 3：为了 `host` 统一而重写 payload

如果第一版试图把所有旧 payload 统一成新模型，会把“对象入口上收”变成“底层实现重写”，导致风险外溢。

控制方式：保留现有 payload，顶层只增加 `command/action/target/compat_source`。

## 成功标准

当以下条件同时满足时，认为第一版 `host` 成功：

- `ops.cli` 顶层出现显式 `host` 对象域
- `host inventory / audit / remote bash / secrets-layout` 可用
- active 文档与 host skill 默认指向 `ops.cli host ...`
- legacy 入口仍可用，但不再作为默认正式路径
- `network / panel / firewall` 仍保持原域，且在文档中被明确标成下一阶段桥接对象
