---
status: archived
owner: AgentPlane maintainers
last_verified: 2026-04-25
superseded_by: null
audience: both
layer: technical
---

# 🔌 1Panel CLI Validation Workflow

结论：1Panel 只保留 `panel|firewall|cronjob|task` 读取面，正式验证走 `projection verification`，不把 1Panel 当验证总入口。

## 📌 当前正式边界

现在要把两类入口分清：

- `onepanel <panel|firewall|cronjob|task>`：provider/debug 读取面
- `projection verification|fixture|ledger`：正式验证与生成物面

也就是说，1Panel 不再承担“验证工作流总入口”，它只保留对象读取和底层排障壳层。

## 当前验证 profile

| profile | target | 角色 | 当前状态 |
| --- | --- | --- | --- |
| `wsl-fixture` | `wsl` | 本地 mutation / regression 面 | 已通过 |
| `prod0-readonly` | `prod0-main` | 升级前只读审计面 | 当前失败，远端 helper 缺失 |

## 当前已确认的问题

`prod0-readonly` 不是“结果不理想”，而是链路本身坏了。  
本轮现场报错是：

- 远端缺少正式 AgentPlane 控制面代码

所以目前 `prod0-readonly` 不能代表 prod0 的 1Panel 状态，只能代表“远端 readonly helper 需要修”。

## 正式命令

### WSL fixture

```bash
agentplane projection fixture plan --target wsl --profile wsl-fixture --repo-root <repo-root>
agentplane projection fixture apply --target wsl --profile wsl-fixture --repo-root <repo-root> --execute
agentplane projection verification run --target wsl --profile wsl-fixture --repo-root <repo-root> --write-report
agentplane projection fixture cleanup --target wsl --profile wsl-fixture --repo-root <repo-root> --execute
```

### prod0 readonly

```bash
agentplane projection verification run --target prod0-main --profile prod0-readonly --repo-root <repo-root>
agentplane projection ledger refresh --target prod0-main --repo-root <repo-root> --write
```

### provider/debug

```bash
agentplane onepanel --env <target> panel get
agentplane onepanel --env <target> firewall search
agentplane onepanel --env <target> task search
```

## 使用原则

1. 只要是“我要证明当前状态”，优先 `projection verification run`。
2. 只要是“我要刷新机器投影”，优先 `projection ledger refresh --write`。
3. 只要是“我要调 provider 原生对象”，才去 `onepanel ...`。
4. `verification-*.json|md` 和 `ledgers/*.json|md` 都是生成物，不手工改。
