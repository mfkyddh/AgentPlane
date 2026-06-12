---
name: "source-command-agentplane-mihomo-openai-tuning"
description: "Diagnose and optimize slow OpenAI/ChatGPT egress on Tencent Cloud hosts when Mihomo is deployed. Benchmark nodes, hot-switch selector, verify improvement."
---

# source-command-agentplane-mihomo-openai-tuning

Use this skill when the user asks to run the migrated source command `agentplane-mihomo-openai-tuning`.

## Command Template

# Tencent Host Mihomo OpenAI Tuning

Use on the remote host side when Mihomo is healthy but OpenAI traffic is slow because the `GPT` selector is pinned to a bad node.

## Rules

- Use on remote host side, not Windows host side
- Benchmark candidate nodes before switching

Full details: `.agents/skills/tencent-host-mihomo-openai-tuning/SKILL.md`

## Overview

Diagnose and optimize slow OpenAI/ChatGPT egress on Tencent Cloud hosts when Mihomo is deployed. Benchmark nodes, hot-switch selector, verify improvement.

## Commands

```bash
agentplane infra
```

## Downstream Docs

See `.agents/skills/tencent-host-mihomo-openai-tuning/SKILL.md` for detailed documentation.
