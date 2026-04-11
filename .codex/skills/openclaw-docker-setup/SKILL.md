---
name: openclaw-docker-setup
description: Install or update OpenClaw in Docker on Ubuntu or WSL, store repository files under infra/compose/openclaw, keep persistent config and workspace data under /data/openclaw, build from a Linux-path source checkout, verify gateway startup, and capture durable environment lessons. Use when Codex is asked to set up OpenClaw with Docker, repair an OpenClaw Docker deployment, or turn OpenClaw installation experience into reusable repo guidance.
---

# OpenClaw Docker Setup

Set up OpenClaw as a local Docker service in this repository, using a compose file under `infra/compose/openclaw`, host persistence under `/data/openclaw`, and a source checkout inside the WSL Linux filesystem.

## Workflow

1. Verify the effective Linux user, home directory, repository path, and Docker access before editing files or creating host directories.
2. Prefer the intended Linux user such as `zqf` for normal Docker work, but use `root` or `sudo` deliberately when creating or fixing `/data/openclaw/*`.
3. Keep the OpenClaw source checkout on a Linux path such as `/root/work/openclaw`; avoid building from `/mnt/c/...` or other Windows-mounted paths for this heavy Node-based image.
4. Store project files under `infra/compose/openclaw/` and keep them minimal: `docker-compose.wsl.yml`, `docker-compose.prod0.yml`, an install helper script, and tracked templates under `templates/services/openclaw.env.example` with the real env kept in `secrets/services/openclaw.env`.
5. Build the image locally from the upstream source checkout unless the user explicitly provides a trusted remote image reference.
6. Persist OpenClaw config under `/data/openclaw/config` and workspace data under `/data/openclaw/workspace`.
7. Pre-create the host directories before first start and make them writable by the container `node` user (uid 1000), or startup and onboarding can fail with permission errors.
8. Publish the tracked Docker ports on `0.0.0.0`, but keep `OPENCLAW_GATEWAY_BIND=lan` inside the container so the host can reach the gateway through Docker port mapping.
9. Use dedicated OpenClaw containers and a dedicated Docker network such as `openclaw_network` instead of attaching OpenClaw to shared infrastructure networks by default.
10. Require or generate a strong `OPENCLAW_GATEWAY_TOKEN` even for local-only installs, then pass it to both the gateway and CLI containers.
11. Keep browser installation, Docker CLI installation, sandboxing, and extension builds opt-in through environment variables instead of enabling them by default.
12. Start the gateway with `docker compose -f docker-compose.wsl.yml up -d --build openclaw-gateway`, ensure the resulting container name is `openclaw-gateway-dev`, then verify container health before running interactive onboarding through `docker compose -f docker-compose.wsl.yml run --rm openclaw-cli ...`.
13. Report the source path, compose path, published ports, persistence paths, bind mode, token state, dedicated network name, and whether at least one model provider key is configured.
14. If you learn a new durable pitfall, update `AGENTS.md` in the same turn and summarize the broader story in `README.md` when it helps future setup work.

## File Layout

Use this repository layout:

```text
infra/compose/openclaw/
  docker-compose.wsl.yml
  docker-compose.prod0.yml
  install-openclaw.sh
```

```text
templates/services/
  openclaw.env.example

secrets/services/
  openclaw.env
```

## Important Config Decisions

Confirm these items when they are not already specified:

- Source checkout path, with a Linux-path default such as `/root/work/openclaw`
- Persistence paths, with defaults `/data/openclaw/config` and `/data/openclaw/workspace`
- Published ports, with defaults `0.0.0.0:18789` and `0.0.0.0:18790`
- Whether OpenClaw should stay on a dedicated Docker network, with `openclaw_network` as the default
- At least one model provider credential such as `OPENAI_API_KEY` or `ANTHROPIC_API_KEY`
- Whether browser dependencies should be baked into the image
- Whether sandbox support is required, which also implies Docker CLI inside the container and docker.sock handling

## Command Pattern

Prefer explicit WSL user targeting:

```bash
wsl -d Ubuntu -u zqf -- bash -lc '...'
```

Create persistence directories and fix ownership:

```bash
sudo mkdir -p /data/openclaw/config /data/openclaw/workspace
sudo chown -R 1000:1000 /data/openclaw/config /data/openclaw/workspace
```

Start the gateway:

```bash
cd /root/work/env_ubuntu/infra/compose/openclaw
docker compose up -d --build openclaw-gateway
```

Run onboarding after the gateway is healthy:

```bash
docker compose run --rm openclaw-cli onboard --mode local --no-install-daemon
docker compose run --rm openclaw-cli doctor
```

## Notes

- OpenClaw's upstream Docker flow defaults the runtime bind to `lan`; that is correct inside a container even when the host port exposure stays loopback-only.
- In this repository, both tracked OpenClaw templates publish the gateway ports on `0.0.0.0`.
- If the user asks for isolation, keep OpenClaw on its own Docker network instead of reusing `zqf_network` or another shared project network.
- If `/data` is root-owned, normal user setup will fail unless the directories are created with elevated privileges first.
- Do not run the first-time install from the Windows-mounted worktree path when a Linux clone can be used instead.
- In this repository's WSL test environments, the canonical gateway container name is `openclaw-gateway-dev`.
- Keep the final report concrete: mention exact source directory, exact compose path, exact host data paths, exact published ports, and whether onboarding was completed.
