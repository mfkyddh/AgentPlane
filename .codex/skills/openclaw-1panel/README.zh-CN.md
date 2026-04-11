# 1Panel Skills

[English](./README.md) | [简体中文](./README.zh-CN.md)

这是保留给历史兼容场景的 direct-API 包。对本仓库来说，默认操作路径已经切到 canonical `CLI-first` repo skills，也就是 `.codex/skills/onepanel-*-ops` 和 `uv run python -m agentplane.cli onepanel ...`。

通用 1Panel 运维技能包，基于 TypeScript 实现。

## 功能特性

- **资源监控**：当前节点状态、仪表盘指标、CPU/内存 Top 进程、监控历史、GPU 历史
- **网站检查**：网站列表与详情、Nginx 配置读取、域名读取、HTTPS 配置读取、SSL 证书读取、网站日志读取
- **应用检查**：应用市场读取、已安装应用状态检查、服务信息读取、端口与连接信息读取
- **已验证的网站写操作**：创建网站、上传网站证书材料、给现有网站绑定 HTTPS
- **已验证的应用写操作**：安装官方应用、更新已安装应用参数
- **容器检查**：容器列表、状态、Inspect、资源统计、日志读取
- **日志检查**：操作日志、登录日志、系统日志文件列表、通用日志文件读取
- **定时任务检查**：定时任务列表与详情、下次执行预览、执行记录、记录日志读取
- **任务中心检查**：任务中心记录与执行中数量
- **节点检查**：节点列表、简化节点列表、节点选项、节点状态读取
- **高风险操作仍预留**：删除、卸载、停止、重启等高风险变更仍保持手动或后续单独验证

## 目录结构

```text
1Panel-skills/
├── SKILL.md                  # 技能说明
├── README.md                 # 英文 README
├── README.zh-CN.md           # 中文 README
├── openclaw.plugin.json      # 可选的 OpenClaw 插件元数据
├── plugin.ts                 # 可选的 OpenClaw 插件入口（TypeScript 源码）
├── package.json              # Node 包元数据
├── tsconfig.json             # TypeScript 类型检查配置
├── tsconfig.build.json       # TypeScript 构建配置
├── agents/
│   └── openai.yaml           # UI 元数据
├── dist/                     # CLI 与可选 OpenClaw 集成使用的预编译产物
│   ├── plugin.js
│   └── scripts/
│       ├── cli.js
│       ├── client.js
│       ├── index.js
│       └── modules/
├── references/
│   └── module-groups.md      # 模块说明与 API 备注
└── scripts/
    ├── cli.ts                # 本地 CLI 入口
    ├── client.ts             # 1Panel 签名客户端
    ├── index.ts              # 模块注册表
    ├── types.ts              # 公共类型
    └── modules/
        ├── monitoring.ts
        ├── websites.ts
        ├── apps.ts
        ├── containers.ts
        ├── logs.ts
        ├── cronjobs.ts
        ├── task-center.ts
        └── nodes.ts
```

## 技能说明

### onepanel-ops

这是一个通用的 1Panel 操作技能。当前实现覆盖查询、读取、状态校验，以及少量已经验证过的低风险写操作；其余高风险变更继续保留为预留定义。

#### 模块列表

| 模块 | 说明 |
|------|------|
| `monitoring` | 仪表盘指标、当前节点状态、Top 进程、监控历史、GPU 历史 |
| `websites` | 网站列表/详情、配置读取、HTTPS 读取、证书读取、网站日志读取 |
| `apps` | 应用市场读取、已安装应用状态检查、服务读取、端口与连接信息 |
| `containers` | 容器列表、状态、Inspect、资源统计、日志读取 |
| `logs` | 操作日志、登录日志、系统日志文件、通用日志读取 |
| `cronjobs` | 定时任务列表/详情、下次执行预览、记录、记录日志、脚本选项 |
| `task-center` | 任务中心记录与执行中数量 |
| `nodes` | 节点列表、节点选项、简化节点列表、节点状态 |

## 快速开始

### 1. 环境要求

- 建议使用 Node.js 18 或更高版本
- 可访问的 1Panel 实例
- 可用的 1Panel API Key
- 目标面板已开启 1Panel API 接口

### 2. 配置 1Panel API

1. 登录 1Panel。
2. 进入 **设置** -> **API 接口**。
3. 开启 API 接口。
4. 复制 API Key。
5. 测试时建议放通客户端 IP：
   - IPv4: `0.0.0.0/0`
   - IPv6: `::/0`
6. 如果启用了 **安全入口**，记录入口 slug，例如 `abc123def`。
7. 在本仓库里，优先不要从工作站直连面板 API。默认做法是先 SSH 到目标主机，再由目标主机本机调用 1Panel API。

1Panel API 鉴权需要这两个 Header：

- `1Panel-Timestamp`
- `1Panel-Token = md5("1panel" + API_KEY + TIMESTAMP)`
- 如果启用了安全入口，还需要：
  - `Origin = <ONEPANEL_BASE_URL 的 origin>`
  - `Referer = <ONEPANEL_BASE_URL 的 origin>/<ONEPANEL_SECURITY_ENTRANCE>/`

`ONEPANEL_BASE_URL` 应该填写面板根地址，例如 `https://panel.example.com:8443`，不要把安全入口路径直接拼进去。
如果目标面板开启了 **域名绑定**，而你又要从主机本机走回环地址访问 API，则应把 `ONEPANEL_BASE_URL` 保持为绑定域名的公网 origin，再额外设置 `ONEPANEL_CONNECT_BASE_URL` 指向真实连接地址，例如 `http://127.0.0.1:2096`。这样请求仍会带正确的 `Host` / `Origin` / `Referer`，但网络路径留在主机本地。

本仓库当前验证过的 0号生产机口径：

- 本地仓库 env：`secrets/services/onepanel-api.env`
- 生产机仓库 env：`/opt/env_ubuntu/secrets/services/onepanel-api.env`
- 逻辑 origin：`https://1panel.zzzai.cloud:8443`
- 本机连接地址：`http://127.0.0.1:2096`
- 安全入口：`0f0e8602e3`

### 3. 安装到代理运行时

如果你的代理运行时支持从本地目录加载技能，可以直接指向当前目录。以 OpenClaw 为例，可用的本地安装方式是：

```bash
mkdir -p ~/.openclaw/skills
ln -s /path/to/1Panel-skills ~/.openclaw/skills/onepanel-ops
```

仓库已经包含 `dist/` 下的预编译运行产物，正常使用时不需要先手动重新构建。

### 4. 配置运行环境变量

```bash
export ONEPANEL_BASE_URL="http://192.168.1.2:9999"
export ONEPANEL_CONNECT_BASE_URL="http://127.0.0.1:2096"
export ONEPANEL_API_KEY="你的 1Panel API Key"
export ONEPANEL_SECURITY_ENTRANCE="abc123def"
export ONEPANEL_TIMEOUT_MS="30000"
export ONEPANEL_SKIP_TLS_VERIFY="false"
```

## CLI 用法

查看支持的模块：

```bash
node dist/scripts/cli.js modules
```

查看某个模块的动作：

```bash
node dist/scripts/cli.js actions monitoring
```

发一个原始签名请求：

```bash
node dist/scripts/cli.js request GET /api/v2/dashboard/base/os
```

在本仓库里，如果目标主机没有稳定的 Node 运行时，优先使用仓库自带的 Python helper：

```bash
python3 /opt/env_ubuntu/ops/scripts/onepanel/api_request.py \
  GET /api/v2/dashboard/base/os \
  --env-file /opt/env_ubuntu/secrets/services/onepanel-api.env
```

执行模块化动作：

```bash
node dist/scripts/cli.js run monitoring getCurrentNode
node dist/scripts/cli.js run websites searchWebsites --input-json '{"page":1,"pageSize":20}'
```

打印当前签名 Header：

```bash
node dist/scripts/cli.js sign
node dist/scripts/cli.js sign --security-entrance abc123def
```

## 可选的 OpenClaw 集成

这个仓库提供两个运行时入口：

- `dist/plugin.js`：OpenClaw 插件入口
- `dist/scripts/cli.js`：可直接执行的本地签名 CLI

OpenClaw 专用的插件元数据定义在 `openclaw.plugin.json` 中，`package.json` 里导出了编译后的插件入口。

## 开发

安装依赖：

```bash
npm install
```

类型检查：

```bash
npm run typecheck
```

只有修改了 TypeScript 源码后才需要重新构建：

```bash
npm run build
```

## 注意事项

1. 不要把真实 API Key 提交到版本控制。
2. 如果返回 `{"code":401,"message":"API 接口密钥错误"}`，优先检查复制的 Key 是否正确，以及 1Panel API 设置是否已经点击“确认”保存。
3. 如果启用了安全入口，而 `/api/v2/...` 仍返回访问保护页或临时禁止访问，优先检查 `ONEPANEL_SECURITY_ENTRANCE`，并确认请求里确实带上了 `Origin` 和 `Referer`。
4. 如果返回 IP 相关鉴权错误，检查白名单配置和当前调用端运行环境的真实出口 IP。
5. 对当前 `prod0-main`，`POST /api/v2/core/settings/api/config/update` 不能通过 API Key 调用；已验证可用的白名单收紧方式是 `POST /api/v2/core/settings/update`，body 为 `{"key":"IpWhiteList","value":"127.0.0.1"}`。
6. 把 `IpWhiteList` 改成 `127.0.0.1` 只能收紧 1Panel 直连监听口；如果公网反代也在同一台主机上，它仍可能以 `127.0.0.1` 身份转发 `/api/v2/...` 给 1Panel，这一点不能误判成“公网 API 已彻底关闭”。
7. 某些节点相关接口可能要求 1Panel Pro 或 XPack。

## 许可证

MIT
