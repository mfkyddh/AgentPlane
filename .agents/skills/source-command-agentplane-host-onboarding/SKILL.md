---
name: "source-command-agentplane-host-onboarding"
description: "Bring a new Ubuntu, WSL, or remote Linux host under AgentPlane management, including bootstrap, SSH topology, 1Panel installation, and SSH security baseline."
---

# source-command-agentplane-host-onboarding

Use this skill when the user asks to run the migrated source command `agentplane-host-onboarding`.

## Command Template

# Host Onboarding Ops

Use when a host is not yet fully managed by AgentPlane. Combines new-host onboarding, optional 1Panel installation, and default SSH hardening baseline.

## Rules

- Inspect host state before installing anything
- SSH baseline is mandatory for new hosts

Full details: `.agents/skills/host-onboarding-ops/SKILL.md`
