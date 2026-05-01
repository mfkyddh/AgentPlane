---
name: agentplane-ingress-ops
description: Use for website and public ingress object search, inspection, verification, publication planning, certificate binding, and ledger refresh through AgentPlane.
---

# AgentPlane Ingress Ops

## Overview

Use this domain skill for public HTTP ingress, website aliases, Cloudflare-backed publication, certificate binding, and ingress ledger refresh. The provider may be 1Panel, nginx-ui, OpenResty, or Cloudflare, but the Agent route is `agentplane ingress ...`.

## Commands

```bash
agentplane ingress search --target <target> --repo-root <repo-root>
agentplane ingress get --target <target> --alias <alias> --repo-root <repo-root>
agentplane ingress verify --target <target> --alias <alias> --repo-root <repo-root>
agentplane ingress plan --target <target> --alias <alias> --operation reconcile --repo-root <repo-root>
agentplane ingress apply --target <target> --alias <alias> --operation reconcile --repo-root <repo-root> --execute
agentplane ingress publish plan --target <target> --config-file <config-file> --cloudflare-env-file <cloudflare-env-file> --repo-root <repo-root>
agentplane ingress publish apply --target <target> --config-file <config-file> --cloudflare-env-file <cloudflare-env-file> --repo-root <repo-root> --execute
agentplane ingress publish verify --target <target> --config-file <config-file> --cloudflare-env-file <cloudflare-env-file> --repo-root <repo-root>
agentplane ingress refresh-ledger --target <target> --repo-root <repo-root> --write
```

## Capability Details

- `verify` checks: website status, domain binding, HTTPS enablement, SSL certificate detail (status, expiry), OpenResty running state.
- `plan reconcile` creates a plan for missing websites; `apply reconcile` executes the plan.
- After `apply`, `verify` is automatically triggered and operation is recorded to ledger.

## Rules

- Use `verify` to prove public behavior, not provider UI status text.
- Certificate material must stay in the intended secrets or provider store; do not paste real certs into tracked files.
- After tracked ingress changes, refresh the ingress ledger.
- Use `site-migration-ops` for multi-step website migration workflows.

## Downstream Docs

- `docs/reference/onepanel-api-contract.md`
- `docs/runbooks/control-plane-agent-execution-flow.md`
