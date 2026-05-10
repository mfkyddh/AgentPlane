---
status: active
owner: AgentPlane maintainers
last_verified: 2026-05-10
audience: both
---

# 设计系统

> 结论：AgentPlane Web UI 采用暗色 Tech/utility 风格，参考 Datadog / GitHub / Sentry。所有页面共享一套 CSS token，确保视觉一致性。

---

## 设计方向

**Tech / utility** — 数据密集、装饰极少、终端气质。

- 目标用户：极客、DevOps、自托管爱好者
- 布局偏好：卡片式、信息密度高
- 色彩策略：暗色背景 + 单色点缀，不做渐变滥用

---

## 色板

所有颜色通过 CSS 变量（token）引用，不直接使用硬编码值。

### 背景

| Token | 值 | 用途 |
|-------|-----|------|
| `--bg-primary` | `#0d1117` | 页面底色 |
| `--bg-secondary` | `#161b22` | 卡片、侧边栏、面板 |
| `--bg-tertiary` | `#1c2128` | 悬停态、表头、输入框 |
| `--bg-overlay` | `#21262d` | 标签背景、badge、代码块 |

### 边框

| Token | 值 | 用途 |
|-------|-----|------|
| `--border` | `#30363d` | 主边框（卡片、面板、分隔线） |
| `--border-muted` | `#21262d` | 次要边框（行内分隔） |

### 前景

| Token | 值 | 用途 |
|-------|-----|------|
| `--fg-primary` | `#e6edf3` | 标题、正文 |
| `--fg-secondary` | `#8b949e` | 次要文本、元数据 |
| `--fg-muted` | `#484f58` | 占位符、禁用态 |

### 强调色

| Token | 值 | 用途 |
|-------|-----|------|
| `--accent-blue` | `#58a6ff` | 主操作、链接、active 状态 |
| `--accent-green` | `#3fb950` | 成功、连接、healthy |
| `--accent-red` | `#f85149` | 错误、断开、critical |
| `--accent-yellow` | `#d29922` | 警告、未知、pending |
| `--accent-purple` | `#bc8cff` | 标签、依赖标记 |
| `--accent-cyan` | `#39d2c0` | 目标标签、辅助信息 |

### 使用约束

- 每个页面最多使用 **2 种强调色**，其中一种为主色（通常 blue）
- 状态色（green/red/yellow）用于语义指示，不算在配额内
- 不使用渐变做背景（品牌图标和 skeleton shimmer 除外）

---

## 字体

| Token | 值 | 用途 |
|-------|-----|------|
| `--font-mono` | `'JetBrains Mono', ui-monospace, 'Cascadia Code', 'Fira Code', Menlo, monospace` | 数值、标签、代码、ID |
| `--font-sans` | `-apple-system, BlinkMacSystemFont, 'Segoe UI', 'Noto Sans', Helvetica, Arial, sans-serif` | 正文、标题 |

### 字号约定

| 场景 | 大小 | 字体 |
|------|------|------|
| KPI 数值 | 28px | mono |
| 页面标题 | 18px | sans, weight 600 |
| 面板标题 | 13px | sans, weight 600 |
| 正文 | 13–14px | sans |
| 标签/badge | 11px | mono |
| 时间戳 | 11px | mono |

### 数值排版

所有数值型数据（端口、计数、百分比）使用 `font-variant-numeric: tabular-nums`。

---

## 间距

| Token | 值 | 用途 |
|-------|-----|------|
| `--radius-sm` | `6px` | 按钮、输入框、小卡片 |
| `--radius-md` | `8px` | 面板、大卡片 |
| `--radius-lg` | `12px` | 模态框、弹出层 |

### 布局间距

| 场景 | 间距 |
|------|------|
| 页面内边距 | 24px |
| 卡片间距 | 16px |
| 面板内边距 | 12–16px |
| 紧凑元素间距 | 8px |

---

## 组件模式

### 状态指示器

**Status Dot** — 圆形指示灯，8px，带 glow shadow：

```html
<span class="status-dot connected"></span>
<span class="status-dot unknown"></span>
<span class="status-dot error"></span>
```

**Status Pill** — 文字标签，11px mono，tinted background：

```html
<span class="status-pill connected">connected</span>
<span class="status-pill unknown">pending</span>
<span class="status-pill error">failed</span>
```

### 卡片 / 面板

标准卡片结构：

```html
<div class="panel">
  <div class="panel-header">
    <span class="panel-title">Title</span>
    <span class="panel-count">3</span>
  </div>
  <div class="panel-body"><!-- content --></div>
</div>
```

### 数据表格

表格头部使用 `--bg-tertiary` 背景 + mono 大写字母标签：

```html
<table class="data-table">
  <thead>
    <tr><th>Column</th></tr>
  </thead>
  <tbody>
    <tr><td class="cell-primary">Value</td></tr>
  </tbody>
</table>
```

### 按钮

Ghost 按钮（次要操作）：

```html
<button class="btn-ghost">Action</button>
```

Primary 按钮（主操作）使用 `--accent-blue` 背景。

### 标签

- `control-plane-tag` — 控制面标签（灰色边框）
- `op-target-tag` — 操作目标（cyan 色调）
- `topo-dep-tag` — 依赖标签（purple 色调）

---

## 布局约定

### 页面结构

```
┌──────────────────────────────────────┐
│ Sidebar (240px) │  Main Content      │
│  - Brand        │  ┌──────────────┐  │
│  - Nav items    │  │ Top Bar      │  │
│  - Status       │  ├──────────────┤  │
│                 │  │ Stats Row    │  │
│                 │  ├──────┬───────┤  │
│                 │  │ Main │ Side  │  │
│                 │  │ 70%  │ 30%   │  │
│                 │  └──────┴───────┘  │
└──────────────────────────────────────┘
```

### 响应式

当前仅支持桌面端（≥1280px）。移动端适配待规划。

---

## Token 文件

| 文件 | 用途 |
|------|------|
| `agentplane/web/static/tokens.css` | CSS 变量 + reset，所有页面共享 |
| `agentplane/web/static/index.html` | Dashboard 主页面（内联组件样式） |

新页面引入方式：

```html
<link rel="stylesheet" href="/static/tokens.css">
```

---

## 反模式（禁止）

| 禁止 | 替代 |
|------|------|
| 硬编码颜色值 | 使用 `var(--xxx)` |
| 渐变背景 | 纯色背景 |
| Emoji 图标 | 文字或 SVG |
| 圆角 + 左边框 accent | 标准 panel 组件 |
| Inter / Roboto 做 display 字体 | `--font-sans` 或 `--font-mono` |
| 填充统计（"10× faster"） | 真实数据或留空 |

---

## 关联文档

- [conventions.md](conventions.md) — 编码与协作规范
- [architecture.md](core/architecture.md) — 技术架构
- [vision.md](core/vision.md) — 项目定位与约束
