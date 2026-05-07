# AgentPlane WebUI

> WebUI 是控制面的可视化视图，不是新的控制面入口。本文基于 design doc 编写。

---

## 架构

```
WebUI (FastAPI + uvicorn) → domain handlers → runtime → providers
     ↑
CLI (argparse) → domain handlers → runtime → providers
```

两者共享同一个 domain 层，WebUI 是一个薄展示层。

---

## 启动

```bash
# 本地开发
agentplane web --host 127.0.0.1 --port 8080

# 生产部署（带认证）
agentplane web --host 0.0.0.0 --port 8080 --token <your-token>

# 通过环境变量设置 token
AGENTPLANE_WEB_TOKEN=<your-token> agentplane web --host 0.0.0.0 --port 8080
```

---

## 技术选型

| 组件 | 选择 | 理由 |
|------|------|------|
| 前端 | Vue 3 CDN 模式 | ~40KB，无需构建工具，响应式数据绑定 |
| 后端 | FastAPI + uvicorn | 现代异步框架，自动 OpenAPI 文档 |
| LLM | Claude API（Haiku） | 成本最低，响应最快 |
| 端口 | 默认 8080 | 可通过 `--port` 配置 |

---

## 功能

### 仪表盘

- 服务器状态卡片：hostname、IP、连接状态、last_seen
- 应用状态表格：name、status、control_plane、public_url
- 数据刷新：轮询 `os.stat` mtime（每 5 秒），仅在有活跃连接时启动

### Agent 聊天

- 自然语言输入 → Claude API → 命令解析 → domain 层执行 → 结果展示
- 仅支持只读命令：`search`、`get`、`verify`、`health`
- 破坏性操作（`apply`、`delete`、`plan`）一律拒绝

---

## API 端点

### REST API

```
GET /api/hosts        — 服务器列表
GET /api/apps         — 应用状态
GET /api/operations   — 操作记录
```

### WebSocket

```
ws://localhost:8080/ws/chat  — Agent 聊天
```

消息格式：
```json
// 客户端 → 服务器
{"type": "chat_message", "payload": {"text": "检查 prod0-main 的应用状态"}}

// 服务器 → 客户端
{"type": "chat_response", "payload": {"text": "正在执行...", "status": "running"}}
{"type": "command_result", "payload": {"command": "app verify", "output": "...", "status": "success"}}
{"type": "error", "payload": {"message": "LLM 调用失败", "code": "LLM_ERROR"}}
```

---

## 认证

- **本地部署（默认）**：无认证
- **生产部署**：通过 `--token` 或 `AGENTPLANE_WEB_TOKEN` 环境变量设置
- 前端 token 存入 `sessionStorage`，后续请求自动附加

---

## 命令白名单

允许的命令动词（只读）：

| 动词 | 示例 | 说明 |
|------|------|------|
| `search` | `app search` | 查询操作 |
| `get` | `infra get` | 获取详情 |
| `verify` | `service verify` | 验证状态 |
| `health` | `infra health` | 健康检查 |

禁止：所有 `apply`、`delete`、`plan` 动词，原始 shell 命令。

---

## 文件结构

```
agentplane/web/
├── __init__.py
├── server.py          # FastAPI 应用，路由注册
├── agent_router.py    # Agent 聊天路由
├── api.py             # REST API 端点
├── models.py          # Pydantic 数据模型
└── static/            # 前端静态文件
    ├── index.html     # Vue 3 CDN
    ├── style.css
    └── app.js
```

---

## 关联文档

- [架构](architecture.md) — 控制面核心合同
- [命令参考](command-reference.md) — CLI 命令
