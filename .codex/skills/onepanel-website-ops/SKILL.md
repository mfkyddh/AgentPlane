---
name: onepanel-website-ops
description: Use when the task is about 1Panel website objects, proxy targets, HTTPS bindings, or public-site verification through the AgentPlane CLI.
---

# 1Panel Website Ops

## Overview

This skill routes formal website-object inspection, verification, and low-risk reconcile planning through `agentplane.cli website`.

## Commands

```bash
uv run python -m agentplane.cli website search --target <target> --repo-root <repo-root>
uv run python -m agentplane.cli website get --target <target> --alias <alias> --repo-root <repo-root>
uv run python -m agentplane.cli website verify --target <target> --alias <alias> --repo-root <repo-root>
uv run python -m agentplane.cli website plan --target <target> --alias <alias> --operation reconcile --repo-root <repo-root>
uv run python -m agentplane.cli website publish plan --target <target> --config-file <config-file> --cloudflare-env-file <cloudflare-env-file> --repo-root <repo-root>
uv run python -m agentplane.cli website publish apply --target <target> --config-file <config-file> --cloudflare-env-file <cloudflare-env-file> --execute --repo-root <repo-root>
uv run python -m agentplane.cli website publish verify --target <target> --config-file <config-file> --cloudflare-env-file <cloudflare-env-file> --repo-root <repo-root>
```

## Rules

- Treat website objects as infrastructure truth, not app-repo truth.
- `website` 是正式公网入口域；对象核验和 `publish` 任务都从这里进入。
- `onepanel website` 已退出公开默认入口，只保留 provider/API substrate 语义。
- After tracked changes, run `uv run python -m agentplane.cli website refresh-ledger --target <target> --repo-root <repo-root> --write`.
