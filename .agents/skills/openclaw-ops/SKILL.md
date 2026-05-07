---
name: openclaw-ops
description: Use for OpenClaw setup or repair decisions, including Docker versus official WSL installation, custom OpenAI-compatible endpoints, Feishu delivery repair, and Windows Chrome bridge checks.
---

# OpenClaw Ops

## Overview

Use this workflow skill for OpenClaw tasks. First choose the lane: repository-managed Docker service, official WSL install, or Windows Chrome bridge repair. After the lane is chosen, keep persistent service state under the normal AgentPlane service, infra, and projection rules.

## Lanes

| Lane | Use when | Primary route |
| --- | --- | --- |
| Docker | OpenClaw should be a repository-managed compose service | `docker-service-setup` plus service verify |
| Official WSL | User wants upstream installer or local gateway | `agentplane-infra-ops` for host route, then documented installer steps |
| Chrome bridge | WSL OpenClaw must control Windows Chrome through CDP | Browser bridge scripts may be implementation helpers, not long-term control-plane truth |

## Commands

```bash
agentplane infra inventory <target> --repo-root <repo-root>
agentplane infra remote bash <target> -- command -v openclaw
agentplane service search --target <target> --repo-root <repo-root>
agentplane service verify --target <target> --name openclaw --repo-root <repo-root>
agentplane projection ledger refresh --target <target> --repo-root <repo-root> --write
```

## Rules

- Do not mix Docker and official installer state without first identifying which lane owns the host.
- Keep API keys and Feishu credentials in `secrets/`.
- Verify gateway status, model endpoint reachability, dashboard token behavior, and channel delivery when relevant.
- Durable bridge helpers belong under implementation assets; the Skill should route and verify, not duplicate scripts.

## Downstream Docs

- `docs/tech-stack.md`
- `agentplane/scripts/browser/README.md`
