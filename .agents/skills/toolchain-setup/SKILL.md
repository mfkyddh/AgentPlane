---
name: toolchain-setup
description: Use for installing or repairing host development toolchains such as Node.js LTS, pnpm/npm mirror settings, Maven, or Java when AgentPlane needs them for a controlled workflow.
---

# Toolchain Setup

## Overview

Use this workflow skill when a host or WSL backend is missing a toolchain required by a formal AgentPlane task. This replaces separate Node.js and Maven setup skills.

Toolchain setup is supporting infrastructure, not a production control-plane object. Keep the work scoped, verify versions, and return to the formal AgentPlane workflow that needed the tool.

## Commands

```bash
agentplane infra remote bash <target> -- node -v
agentplane infra remote bash <target> -- npm -v
agentplane infra remote bash <target> -- java -version
agentplane infra remote bash <target> -- mvn -v
agentplane infra audit <target> --repo-root <repo-root>
```

## Rules

- Use the host's intended backend route: local PowerShell for Windows host work, `wsl.exe -e` for WSL, and `infra remote bash` for remote Linux.
- Prefer LTS/runtime versions already declared by project docs or CI.
- Mirror settings may be host-local; do not commit generated user-level config.
- Verify the exact versions and package registry/mirror after installation.

## Downstream Docs

- `docs/reference/tech-stack.md`
- `docs/reference/cross-platform.md`
