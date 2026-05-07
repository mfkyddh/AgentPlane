---
name: host-onboarding-ops
description: Use for bringing a new Ubuntu, WSL, or remote Linux host under AgentPlane management, including bootstrap inspection, SSH topology, 1Panel installation, and the default SSH security baseline.
---

# Host Onboarding Ops

## Overview

Use this workflow skill when a host is not yet fully managed by AgentPlane. It combines new-host onboarding, optional 1Panel installation, and the default SSH hardening baseline.

Root SSH or password login is a break-glass exception, not the default onboarding route. If the user explicitly asks for it, document the risk and return to the security baseline after the emergency.

## Commands

```bash
agentplane bootstrap inspect-local --repo-root <repo-root>
agentplane bootstrap doctor --repo-root <repo-root>
agentplane bootstrap init-secrets --repo-root <repo-root>
agentplane bootstrap verify-secrets --repo-root <repo-root>
agentplane infra inventory <target> --repo-root <repo-root>
agentplane infra audit <target> --repo-root <repo-root>
agentplane infra remote bash <target> -- uname -a
agentplane infra network audit <target> --repo-root <repo-root>
```

## Rules

- Prefer key-only SSH, no root login, minimal allowed inbound ports, and fail2ban for public hosts.
- Use `secrets/hosts/<target>/` for host truth; do not commit PEM files or generated credentials.
- Install or repair 1Panel only after host identity, SSH route, and storage layout are understood.
- Verify effective runtime state (`sshd -T`, firewall status, service status) instead of trusting config file text.

## Downstream Docs

- `docs/tutorials/add-new-server.md`
- `docs/runbooks/bootstrap-secrets.md`
- `docs/tech-stack.md`
