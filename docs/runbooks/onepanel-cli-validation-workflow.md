# 1Panel CLI Validation Workflow

## 当前正式边界

现在要把两类入口分清：

- `onepanel <panel|firewall|cronjob|task>`：provider/debug 读取面
- `projection verification|fixture|ledger`：正式验证与生成物面

也就是说，1Panel 不再承担“验证工作流总入口”，它只保留对象读取和底层排障壳层。

## 当前验证 profile

| profile | target | 角色 | 当前状态 |
| --- | --- | --- | --- |
| `wsl-fixture` | `wsl` | 本地 mutation / regression 面 | 已通过 |
| `prod2-readonly` | `prod2-main` | 现场只读审计面 | 未在本轮重点复核 |
| `prod0-readonly` | `prod0-main` | 升级前只读审计面 | 当前失败，远端 helper 缺失 |

## 当前已确认的问题

`prod0-readonly` 不是“结果不理想”，而是链路本身坏了。  
本轮现场报错是：

- 远端缺少 `/opt/agentplane/agentplane/scripts/onepanel/api_request.py`

所以目前 `prod0-readonly` 不能代表 prod0 的 1Panel 状态，只能代表“远端 readonly helper 需要修”。

## 正式命令

### WSL fixture

```bash
uv run python -m agentplane.cli projection fixture plan --target wsl --profile wsl-fixture --repo-root <repo-root>
uv run python -m agentplane.cli projection fixture apply --target wsl --profile wsl-fixture --repo-root <repo-root> --execute
uv run python -m agentplane.cli projection verification run --target wsl --profile wsl-fixture --repo-root <repo-root> --write-report
uv run python -m agentplane.cli projection fixture cleanup --target wsl --profile wsl-fixture --repo-root <repo-root> --execute
```

### prod0 readonly

```bash
uv run python -m agentplane.cli projection verification run --target prod0-main --profile prod0-readonly --repo-root <repo-root>
uv run python -m agentplane.cli projection ledger refresh --target prod0-main --repo-root <repo-root> --write
```

### provider/debug

```bash
uv run python -m agentplane.cli onepanel --env <target> panel get
uv run python -m agentplane.cli onepanel --env <target> firewall search
uv run python -m agentplane.cli onepanel --env <target> task search
```

## 使用原则

1. 只要是“我要证明当前状态”，优先 `projection verification run`。
2. 只要是“我要刷新机器投影”，优先 `projection ledger refresh --write`。
3. 只要是“我要调 provider 原生对象”，才去 `onepanel ...`。
4. `verification-*.json|md` 和 `ledgers/*.json|md` 都是生成物，不手工改。
