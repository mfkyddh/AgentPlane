# Control Plane Legacy Migration

## 目的

本文定义旧脚本、旧 skill、旧 runbook、旧第二控制面向 `AgentPlane` 正式控制面的收敛路径。

## 适用范围

适用于以下遗留形态：

- 旧 shell 脚本仍是主入口
- 旧 skill 直接教 Agent 拼 SSH 或调用历史脚本
- 旧 runbook 承载了实际执行逻辑
- 历史 inventory、摘要或说明文档与现场脱节

## 正式入口

迁移后的正式入口必须是 `uv run python -m agentplane.cli ...`。

## 识别第二控制面

出现以下任一情况，应视为第二控制面信号：

1. README 或 skill 先推荐脚本而不是正式 CLI。
2. 正式流程只能在 runbook 中逐步手工执行，CLI 没有对应入口。
3. 历史脚本与正式 CLI 都能改同一类对象，但合同不同。
4. inventory 真源只能靠人工写 JSON 维持。

## 收敛步骤

### 1. 识别旧入口

先明确：

- 旧脚本路径
- 旧 skill 名称
- 旧 runbook 文件
- 旧台账文件

### 2. 明确正式替代入口

对每个旧入口，给出正式 CLI 对应物：

```bash
uv run python -m agentplane.cli --help
uv run python -m agentplane.cli host remote bash <target> --help
```

### 3. 标注兼容状态

当旧入口暂时还需要保留时，必须显式标注：

- 这是兼容入口
- 它不是正式主路径
- 它的退役目标是什么

### 4. 修改 skill 与文档路由

把 skill、README、runbook 的主入口切回正式 CLI，再把旧入口放到“兼容说明”或“历史说明”。

### 5. 收敛事实落盘

把旧台账、旧摘要、旧文档中的关键事实迁回正式 `inventory` 与 `ledger`。

### 6. 验证迁移结果

迁移后至少确认：

- 新文档默认引用正式 CLI
- 旧脚本不再是第一建议
- skill 默认路线已切换
- 正式 `inventory/ledger` 可以支撑现场对账

## 兼容入口说明

下列入口在过渡期内可能仍存在，但必须明确属于兼容态：

- `agentplane/scripts/remote/run_remote_bash.sh`
- 各类历史 shell wrapper
- 旧 skill 中的脚本型主路径
- `agentplane/scripts/onepanel/api_request.py`、`app_lifecycle.py`、`project_lifecycle.py` 这类 compat helper

这些入口只能作为“过渡态说明”，不得重新写成默认路径。

## 最小命令示例

正式入口：

```bash
uv run python -m agentplane.cli host remote bash prod0-main --repo-root <repo-root> --dry-run
uv run python -m agentplane.cli host inventory prod0-main --repo-root <repo-root>
```

历史上曾存在 `uv run python -m agentplane.cli remote bash ...`、`uv run python -m agentplane.cli inventory ...` 等顶层入口；当前正式入口已经收口到 `host` 对象域与其他正式对象域，这些旧命令不再被 parser 接受。

兼容入口说明示例：

```text
agentplane/scripts/remote/run_remote_bash.sh 属于 compat 入口，只用于历史流程过渡，不再作为正式主路径。
```

## 禁止事项

1. 不要把兼容入口重新包装成主入口。
2. 不要在迁移中制造新的第二控制面。
3. 不要让旧 runbook 与新 runbook 对同一动作给出不同主路径。
4. 不要迁移了入口却不迁移 `inventory/ledger` 对齐逻辑。

## 关联文档

- [control-plane.md](../architecture/control-plane.md#principles)
- [control-plane.md](../architecture/control-plane.md#inventory-and-ledger-projection)
- [control-plane-agent-execution-flow.md](control-plane-agent-execution-flow.md)
- [powershell-wsl-remote-bash.md](powershell-wsl-remote-bash.md)
