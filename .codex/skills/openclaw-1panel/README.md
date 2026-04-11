# 1Panel Skills

[English](./README.md) | [简体中文](./README.zh-CN.md)

Legacy direct-API package for historical compatibility only. In this repository, the default operator path is the canonical `CLI-first` repo skills under `.codex/skills/onepanel-*-ops` and `uv run python -m agentplane.cli onepanel ...`.

TypeScript-based general-purpose 1Panel operations skill.

## Features

- **Resource monitoring**: current node metrics, dashboard metrics, top CPU and memory processes, monitor history, GPU history
- **Website inspection**: website list and detail, Nginx config reads, domain reads, HTTPS config reads, SSL certificate reads, website log reads
- **Application inspection**: app catalog reads, installed app status checks, service reads, port and connection info reads
- **Verified website writes**: create websites, upload website SSL materials, and bind HTTPS for existing sites
- **Verified application writes**: install official apps and update installed app parameters
- **Container inspection**: container list, status, inspect, stats, and log reads
- **Log inspection**: operation logs, login logs, system log file list, generic log file reads
- **Cronjob inspection**: cronjob list and detail, next-run preview, execution records, record log reads
- **Task center inspection**: task center records and executing count
- **Node inspection**: node list, simple node list, node options, and node status reads
- **Destructive operations remain reserved**: delete, uninstall, stop, restart, and other higher-risk mutations stay manual until explicitly verified

## Project Layout

```text
1Panel-skills/
├── SKILL.md                  # Skill instructions
├── README.md                 # English README
├── README.zh-CN.md           # Chinese README
├── openclaw.plugin.json      # Optional OpenClaw plugin metadata
├── plugin.ts                 # Optional OpenClaw plugin entry (TypeScript source)
├── package.json              # Node package metadata
├── tsconfig.json             # TypeScript typecheck config
├── tsconfig.build.json       # TypeScript build config
├── agents/
│   └── openai.yaml           # UI metadata
├── dist/                     # Prebuilt runtime files used by CLI and optional OpenClaw integration
│   ├── plugin.js
│   └── scripts/
│       ├── cli.js
│       ├── client.js
│       ├── index.js
│       └── modules/
├── references/
│   └── module-groups.md      # Module overview and API notes
└── scripts/
    ├── cli.ts                # Local CLI entry
    ├── client.ts             # Signed 1Panel API client
    ├── index.ts              # Module registry
    ├── types.ts              # Shared types
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

## Skill Overview

### onepanel-ops

General-purpose 1Panel operations skill. The current implementation covers inspection plus a small set of verified low-risk writes for app install and website provisioning, while keeping higher-risk mutations reserved.

#### Modules

| Module | Scope |
|------|------|
| `monitoring` | Dashboard metrics, current node status, top processes, monitor history, GPU history |
| `websites` | Website list/detail, config reads, HTTPS reads, certificate reads, website log reads |
| `apps` | App catalog reads, installed app status checks, service reads, port and connection info |
| `containers` | Container list, status, inspect, stats, and log reads |
| `logs` | Operation logs, login logs, system log files, generic log reads |
| `cronjobs` | Cronjob list/detail, next-run preview, records, record logs, script options |
| `task-center` | Task center record reads and executing count |
| `nodes` | Node list, node options, simple list, and node status |

## Quick Start

### 1. Requirements

- Node.js 18 or newer recommended
- A reachable 1Panel instance
- A valid 1Panel API key
- 1Panel API interface enabled on the target panel

### 2. Configure 1Panel API Access

1. Log in to 1Panel.
2. Open **Settings** -> **API Interface**.
3. Enable the API interface.
4. Copy the API key.
5. Add your client IP or allow all for testing:
   - IPv4: `0.0.0.0/0`
   - IPv6: `::/0`
6. If **Security Entrance** is enabled, record the entrance slug, for example `abc123def`.
7. In this repository, prefer SSHing into the target host and calling the API from the host itself instead of going direct from a workstation.

1Panel API authentication requires:

- `1Panel-Timestamp`
- `1Panel-Token = md5("1panel" + API_KEY + TIMESTAMP)`
- when Security Entrance is enabled:
  - `Origin = <ONEPANEL_BASE_URL origin>`
  - `Referer = <ONEPANEL_BASE_URL origin>/<ONEPANEL_SECURITY_ENTRANCE>/`

Set `ONEPANEL_BASE_URL` to the panel root such as `https://panel.example.com:8443`, not to the security entrance path.
If the panel also enables **BindDomain**, keep `ONEPANEL_BASE_URL` set to the bound public origin and add `ONEPANEL_CONNECT_BASE_URL` for the actual local socket such as `http://127.0.0.1:2096`.

Verified `prod0-main` repository layout:

- local env: `secrets/services/onepanel-api.env`
- remote env: `/opt/env_ubuntu/secrets/services/onepanel-api.env`
- logical origin: `https://1panel.zzzai.cloud:8443`
- local connect address: `http://127.0.0.1:2096`
- security entrance: `0f0e8602e3`

### 3. Install into an Agent Runtime

If your agent runtime supports repository-backed local skills, point it at this directory. For OpenClaw, one workable local install is:

```bash
mkdir -p ~/.openclaw/skills
ln -s /path/to/1Panel-skills ~/.openclaw/skills/onepanel-ops
```

The repository already includes prebuilt runtime files under `dist/`, so normal use does not require rebuilding before loading the skill.

### 4. Configure Runtime Variables

```bash
export ONEPANEL_BASE_URL="http://192.168.1.2:9999"
export ONEPANEL_CONNECT_BASE_URL="http://127.0.0.1:2096"
export ONEPANEL_API_KEY="YOUR_1PANEL_API_KEY"
export ONEPANEL_SECURITY_ENTRANCE="abc123def"
export ONEPANEL_TIMEOUT_MS="30000"
export ONEPANEL_SKIP_TLS_VERIFY="false"
```

## CLI Usage

List supported modules:

```bash
node dist/scripts/cli.js modules
```

List actions in one module:

```bash
node dist/scripts/cli.js actions monitoring
```

Send a raw signed request:

```bash
node dist/scripts/cli.js request GET /api/v2/dashboard/base/os
```

In this repository, if the target host does not have a stable Node runtime, prefer the checked-in Python helper:

```bash
python3 /opt/env_ubuntu/ops/scripts/onepanel/api_request.py \
  GET /api/v2/dashboard/base/os \
  --env-file /opt/env_ubuntu/secrets/services/onepanel-api.env
```

Run a grouped module action:

```bash
node dist/scripts/cli.js run monitoring getCurrentNode
node dist/scripts/cli.js run websites searchWebsites --input-json '{"page":1,"pageSize":20}'
```

Print the current auth headers:

```bash
node dist/scripts/cli.js sign
node dist/scripts/cli.js sign --security-entrance abc123def
```

## Optional OpenClaw Integration

This repository exposes two runtime entrypoints:

- `dist/plugin.js`: OpenClaw plugin entry
- `dist/scripts/cli.js`: signed CLI for direct local execution

The OpenClaw-specific plugin metadata is defined in `openclaw.plugin.json`, and the package exports the compiled plugin entry through `package.json`.

## Development

Install dependencies:

```bash
npm install
```

Typecheck:

```bash
npm run typecheck
```

Rebuild only after changing TypeScript source files:

```bash
npm run build
```

## Notes

1. Do not commit real API keys into version control.
2. If you receive `{"code":401,"message":"API 接口密钥错误"}`, first verify the copied key and confirm the 1Panel API settings were saved.
3. If the panel enables Security Entrance and `/api/v2/...` still returns a guard page or a temporary-access denial, verify `ONEPANEL_SECURITY_ENTRANCE` and make sure both `Origin` and `Referer` are being sent.
4. If you receive an IP-related auth error, verify the whitelist and the actual outbound IP of the caller runtime.
5. On current `prod0-main`, `POST /api/v2/core/settings/api/config/update` is blocked for API-key-authenticated callers. The verified API-key path for tightening the whitelist is `POST /api/v2/core/settings/update` with body `{"key":"IpWhiteList","value":"127.0.0.1"}`.
6. `IpWhiteList=127.0.0.1` protects the direct panel listener. It does not automatically disable API calls that are re-proxied by another local reverse proxy on the same host.
7. Some node-related endpoints may require 1Panel Pro or XPack.

## License

MIT
