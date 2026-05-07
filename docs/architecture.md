# AgentPlane 架构

> 本文是 AgentPlane 架构的唯一正文真源。合并了原 control-plane.md、architecture-overview.md、agentplane-app-collaboration.md、linux-governance.md 和 control-plane-authoring.md 的核心内容。

---

## 一句话理解 AgentPlane

```
人类说目标 → AI 匹配 Skill → CLI 执行操作 → 验证结果 → 写回投影
```

AgentPlane 不直接操作服务器，而是通过**标准化入口**操作，每一步都留下**可追溯的证据**。

---

## 三层投影模型

投影是从**真源**派生出的**只读视图**。就像数据库的视图一样，投影不存储原始数据，而是从真源计算得出。

```
┌─────────────────────────────────────────────────────────────┐
│                    第三层：App Summary                        │
│                    （人类可读摘要）                            │
│                    回答"当前正式口径是什么"                    │
└─────────────────────────────────────────────────────────────┘
                              ↑ 派生自
┌─────────────────────────────────────────────────────────────┐
│                    第二层：Object Ledgers                     │
│                    （机器派生证据）                            │
│                    回答"最近一次验证结果是什么"                │
└─────────────────────────────────────────────────────────────┘
                              ↑ 派生自
┌─────────────────────────────────────────────────────────────┐
│                    第一层：Host Inventory                     │
│                    （非敏感台账）                              │
│                    回答"该 target 有哪些受管对象"              │
└─────────────────────────────────────────────────────────────┘
                              ↑ 来源
┌─────────────────────────────────────────────────────────────┐
│                    真源：Git 配置 + Live State                │
│                    inventory.json + 现场命令/API              │
└─────────────────────────────────────────────────────────────┘
```

### 真源优先级

```
Live State（现场状态）> Inventory（台账）> Ledger（证据）> Runbook（文档）
```

Live State 优先级最高，因为它是"实际发生了什么"，而不是"我们希望发生什么"。

### 标准执行闭环

```
Plan（计划）→ Apply（执行）→ Verify（验证）
    ↓
Ledger（写证据）→ Inventory（刷新台账）→ Doc-Sync（同步文档）
```

---

## CLI 合同

### 命令形态

```bash
agentplane <domain> <surface> <verb> [flags]
```

- `<surface>` 可以是 `object`，也可以是更高层的任务面或工作流面
- 新增能力时优先向统一语法收敛

### Verbs

对象面：`search`、`get`、`plan`、`apply`、`verify`、`refresh-ledger`

工作流面：`suite`、`run`、`fixture`、`onboard`、`migrate`、`doctor`

### 公共 Flags

- `--target` 或 `--env`
- `--repo-root`
- `--json`
- `--write`
- `--dry-run` 与 `--execute` 互斥

### 输出合同

- 机器可解析结果写 `stdout`
- 诊断、提示、警告写 `stderr`
- 默认文本模式面向人类；`--json` 模式面向 Agent

### 错误 Envelope

```json
{
  "ok": false,
  "error": {
    "code": "onepanel.object_not_found",
    "hint": "use search first",
    "message": "website token not found"
  },
  "payload": null,
  "evidence": [],
  "artifacts": []
}
```

---

## 域边界

| 域 | 管什么 | 不管什么 |
|---|---|---|
| `infra` | 基础设施治理（主机、网络、Secrets、自动化） | provider/debug 原生对象 |
| `service` | 受管运行服务对象与稳定运行态操作 | raw provider id/name |
| `app` | catalog object 与正式交付流程 | 运行态 restart/reconcile |
| `ingress` | 公网入口对象与发布任务 | provider/debug 原生对象 |
| `projection` | runtime-env、verification、fixture、ledger | 业务真源对象 |
| `onepanel` | 1Panel provider/debug 对象（panel、firewall、cronjob、task） | 正式入口 |

### 对象面 vs 工作流面

**对象面**适合：边界稳定、选择器稳定、动作集合清晰、结果可验证

**工作流面**适合：跨主机、多阶段切换、依赖现场判断、失败补偿复杂

---

## 任务入口模型

`task-entry` 是面向 Agent 的正式任务入口：

1. 名称表达任务结果，而不是底层实现
2. 输入优先使用稳定业务引用
3. 内部可以解析并操作多个对象
4. 输出必须是 Agent 可继续消费的稳定结果

---

## 跨平台执行模型

### 执行路径

```
Windows 宿主
  ├── Windows 原生命令 → pwsh
  ├── 需要 Linux 环境 → wsl.exe -e <程序> <参数>
  │   └── 需要管道/重定向 → wsl.exe bash -lc "cmd1 | cmd2 > out"
  └── 远程 Linux → agentplane infra remote bash
```

### 核心约束

- Windows 和 WSL **共用同一份源码 checkout**
- 每个物理 checkout **只保留一个 `.venv`**
- 不设置平台专属的 `UV_PROJECT_ENVIRONMENT`
- 跨平台路径处理优先使用 runtime/path policy

### Runtime Backend 注册

```python
@register_backend("type")
class SomeBackend:
    ...
```

Backend 自注册模式：Windows → WSL → SSH → Linux native，由 resolver 自动选择。

---

## AgentPlane 与应用层协作

### 职责边界

**AgentPlane 负责**：
- 管理 Linux 主机、SSH 连接、密钥和生产 secrets
- 管理 1Panel、OpenResty、Docker、PostgreSQL、Redis、MinIO 等基础设施
- 管理正式部署、发布切换、回滚、inventory

**应用层项目负责**：
- 业务代码、测试、Dockerfile、镜像构建脚本
- `deploy/agentplane/contract.yaml`（非敏感交付合同）
- 不保存生产 secrets、SSH 密钥、正式 inventory

### 应用交付合同

每个应用仓库必须提供 `deploy/agentplane/contract.yaml`：

```yaml
schema_version: 2
app_id: sub2api
artifact:
  build_command: bash deploy/build-runtime-artifacts.sh
  output_path: dist/oplinux
packaging:
  image_name: sub2api-prod
  image_tag_rule: <upstream>-zzz.<yyyymmdd>.v<n>.g<gitsha>
runtime:
  kind: compose
  container_name: sub2api-prod
  container_port: 8080
  host_binding: 127.0.0.1:18080
  healthcheck:
    path: /health
    expected_status: 200
```

### 容器命名

- 正式应用：`<app>-prod`
- WSL 开发：`<app>-dev`
- 基础设施：显式稳定名（如 `postgres18-prod`）

---

## WebUI 架构

WebUI 是控制面的可视化视图，不是新的控制面入口。

```
WebUI (FastAPI + uvicorn) → domain handlers → runtime → providers
     ↑
CLI (argparse) → domain handlers → runtime → providers
```

两者共享同一个 domain 层，WebUI 是一个薄展示层。

- 启动：`agentplane web --host 127.0.0.1 --port 8080`
- 前端：Vue 3 CDN 模式，无需构建工具
- 后端：FastAPI + uvicorn
- Agent 聊天：通过 Claude API，仅支持只读命令

---

## Skill 路由

Skill 负责路由正式入口、提示前置检查、说明验证与回写。Skill 不得绕过 `agentplane.cli` 演化成第二实现。

正式入口优先级：
```
agentplane.cli > internal implementation asset > runbook > ad-hoc shell
```

---

## Maintainer Authoring 规则

### 治理资产闭环

| 资产 | 角色 | 约束 |
|---|---|---|
| 代码 | 定义正式能力 | 先有 CLI，再补周边 |
| 模板 | 沉淀稳定输入骨架 | 不承载一次性现场上下文 |
| skill | Agent 路由层 | 不变成第二实现 |
| 文档 | 长期合同与专题解释 | 架构页讲边界，runbook 讲流程 |
| 测试 | 回归与约束 | 冻结 CLI 合同 |

### Skill 同步门禁

任何改变正式行为的变更，都必须同步检查 `.agents/skills`。不得把"后续再补 skill"作为完成口径。

---

## 关联文档

- [入门指南](getting-started.md) — 快速了解
- [命令参考](command-reference.md) — 所有 CLI 命令
- [技术栈](tech-stack.md) — 技术选型与跨平台规范
- [WebUI](webui.md) — WebUI 架构和使用
