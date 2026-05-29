---
name: "source-command-agentplane-toolchain-setup"
description: "Install or repair host development toolchains such as Node.js LTS, pnpm/npm mirror settings, Maven, or Java when AgentPlane needs them."
---

# source-command-agentplane-toolchain-setup

Use this skill when the user asks to run the migrated source command `agentplane-toolchain-setup`.

## Command Template

# Toolchain Setup

Use when a host or WSL backend is missing a toolchain required by a formal AgentPlane task.

## Rules

- Only install what's needed for the current task
- Verify installation after setup

Full details: `.agents/skills/toolchain-setup/SKILL.md`
