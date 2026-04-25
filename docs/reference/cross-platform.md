---
status: active
owner: AgentPlane maintainers
last_verified: 2026-04-24
superseded_by: null
---

# 跨平台工作流规范

结论：Windows/WSL/Linux 跨平台开发规范，单份源码、单虚拟环境、正式 CLI 统一入口。

> 本文档定义 AgentPlane 在 Windows + WSL 双环境下的完整工作流规范。核心约束见 `AGENTS.md` 必读摘要。

---

## Windows 宿主规范

| # | 规则 | 级别 | 原因 |
|---|------|------|------|
| 1 | 默认入口 Shell 使用 `pwsh`（PowerShell Core） | 🔴 | `cmd` 语法差异大，易出错 |
| 2 | `git`、`uv`、`pnpm`、测试等宿主子命令直接在 `pwsh` 中运行 | 🟡 | 减少 Shell 切换开销 |
| 3 | 需要 Linux 能力时，优先用 `wsl.exe -e <程序> <参数>` | 🟡 | 直接调用 WSL 程序，避免额外 Shell 层 |
| 4 | 只有需要 WSL 侧 Shell 特性（如管道、重定向）时才用 `wsl.exe bash -lc` | 🟢 | 减少不必要的 Shell 包装 |

### Shell 选择决策

```
需要执行命令
  ├── Windows 原生命令 → pwsh
  ├── 需要 Linux 环境 → wsl.exe -e <程序> <参数>
  │   └── 需要管道/重定向 → wsl.exe bash -lc "cmd1 | cmd2 > out"
  └── 远程 Linux → agentplane infra remote bash
```

---

## WSL 后端规范

| # | 规则 | 级别 | 原因 |
|---|------|------|------|
| 1 | Windows 和 WSL **共用同一份源码 checkout** | 🔴 | 避免两份代码不同步 |
| 2 | WSL 通过 Resolver 提供的 `/mnt/<盘符>/...` 绑定访问源码 | 🟢 | 这是系统提供的映射机制 |
| 3 | 不要仅为运行 WSL 操作而 clone 第二份仓库 | 🔴 | 会造成配置分叉和维护负担 |
| 4 | 避免两个 Shell（Windows + WSL）同时执行包管理器写入 | 🟡 | 防止 `.venv` 或 `node_modules` 损坏 |

---

## Linux / macOS 规范

| # | 规则 | 级别 | 原因 |
|---|------|------|------|
| 1 | 直接使用本地 POSIX Shell 执行本地命令 | 🟡 | 原生支持，无需额外适配 |
| 2 | 远程 Linux 操作应走：`pwsh → agentplane.cli → WSL/SSH backend` | 🔴 | 保持统一入口，不要手写多层命令 |

---

## 虚拟环境规范

| # | 规则 | 级别 | 原因 |
|---|------|------|------|
| 1 | Python 项目统一使用 `uv` 进行依赖安装和环境管理 | 🟡 | `uv` 速度快、行为一致 |
| 2 | 每个物理 checkout **只保留一个 `.venv`** | 🔴 | 禁止创建 `.venv-win`、`.venv-wsl` 等平台变种 |
| 3 | **不要**设置 `UV_PROJECT_ENVIRONMENT` 为平台相关路径 | 🔴 | 让 `uv` 自动使用根目录 `.venv` |
| 4 | Node.js 项目统一使用 `pnpm` | 🟡 | 速度快、磁盘省 |
| 5 | 临时 Node 二进制优先用 `pnpm dlx ...` | 🟡 | 避免全局安装 |

### 为什么单虚拟环境

双环境（`.venv-win` + `.venv-wsl`）会导致：
- 依赖版本不同步，同一个 bug 在一个环境能复现、另一个不能
- `uv.lock` 与实际安装的包不一致
- 磁盘浪费（两份近乎相同的依赖树）

正确做法：`uv` 在 WSL 侧通过 `/mnt/` 访问同一个 `.venv`，或仅在 Windows 侧运行。
