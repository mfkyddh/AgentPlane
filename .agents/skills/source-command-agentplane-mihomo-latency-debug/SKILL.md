---
name: "source-command-agentplane-mihomo-latency-debug"
description: "Diagnose why a domain is slow from Windows when Clash Nyanpasu or Mihomo is involved. Compare latency, identify delay source, apply reversible mitigations."
---

# source-command-agentplane-mihomo-latency-debug

Use this skill when the user asks to run the migrated source command `agentplane-mihomo-latency-debug`.

## Command Template

# Windows Mihomo Cloudflare Latency Debug

Use from the Windows host side. Separates five slow points: Cloudflare edge latency, DNS, TUN, AAAA handling, and origin access.

## Rules

- Apply only reversible Windows-side mitigations (DNS changes, hosts overrides)
- Benchmark before and after each change

Full details: `.agents/skills/windows-mihomo-cloudflare-latency-debug/SKILL.md`

## Overview

Diagnose why a domain is slow from Windows when Clash Nyanpasu or Mihomo is involved. Compare latency, identify delay source, apply reversible mitigations.

## Commands

```bash
agentplane infra
```

## Downstream Docs

See `.agents/skills/windows-mihomo-cloudflare-latency-debug/SKILL.md` for detailed documentation.
