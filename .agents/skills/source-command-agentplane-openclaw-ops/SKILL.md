---
name: "source-command-agentplane-openclaw-ops"
description: "OpenClaw setup or repair decisions, including Docker vs official WSL installation, custom OpenAI-compatible endpoints, Feishu delivery repair, and Windows Chrome bridge checks."
---

# source-command-agentplane-openclaw-ops

Use this skill when the user asks to run the migrated source command `agentplane-openclaw-ops`.

## Command Template

# OpenClaw Ops

Use for OpenClaw tasks. First choose the lane: repository-managed Docker service, official WSL install, or Windows Chrome bridge repair.

## Rules

- Keep persistent service state under normal AgentPlane service, infra, and projection rules
- Choose lane before executing

Full details: `.agents/skills/openclaw-ops/SKILL.md`
