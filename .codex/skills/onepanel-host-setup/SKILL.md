---
name: onepanel-host-setup
description: Use when Codex needs to install, reinstall, migrate, or repair 1Panel on Ubuntu, WSL, or remote Ubuntu hosts in this repository context, especially when persistent 1Panel data should live under /data/1panel or when startup, port exposure, and panel access must be verified after setup.
---

# 1Panel Host Setup

Install or repair 1Panel with the official host installer while keeping this repository's hosts consistent. Prefer fresh installs that set the base directory to `/data`, which yields runtime data under `/data/1panel`.

## Workflow

1. Identify the target context before changing anything:
   - local WSL or local Ubuntu host
   - remote Ubuntu host reached through the repository SSH aliases
   - fresh install, reinstall, or repair of an existing 1Panel
2. Check prerequisites before running the installer:
   - `systemd` is PID 1
   - Docker exists and the daemon is running
   - the chosen panel port is free
   - `command -v 1panel` and `/usr/local/bin/1pctl` show whether 1Panel is already installed
3. Prefer the official online installer or the current official release package from the 1Panel docs.
4. For fresh installs, set the install base directory to `/data`, not `/opt`. The expected runtime directory after install is `/data/1panel`.
5. If the installer detects existing Docker on a China-network host and asks whether to rewrite Docker mirror settings, default to `n` unless the user explicitly wants Docker mirror changes.
6. Choose a free panel port, a non-default secure entrance, and strong credentials. On WSL, validate both the Linux-side URL and the Windows-side `http://127.0.0.1:<port>/<entrance>`.
7. After installation or repair, verify:
   - `1panel version`
   - `systemctl is-active 1panel-core 1panel-agent`
   - `ss -ltnp | grep ":<port>"`
   - `curl -I http://127.0.0.1:<port>/<entrance>`
8. If the task is a normalization from a legacy `/opt/1panel` install to `/data/1panel`, inspect the current `1pctl` base-dir settings and service files before moving data. Do not guess a migration sequence.
9. Record the final URL, panel port, entrance, username, data directory, and whether the host is WSL or remote.

## WSL Notes

- WSL installs still need `systemd` enabled; do not assume older WSL behavior.
- When automating the interactive installer in WSL, account for the extra China-region Docker mirror prompt if it appears before the panel port prompt.
- Published access from Windows is usually through `127.0.0.1:<port>`; also capture the WSL internal IP for Linux-side checks.

## Remote Host Notes

- In this repository, prefer the project SSH aliases from `secrets/ssh/config`.
- Use a sudo-capable account and run administrative steps through `sudo` unless a task explicitly requires direct `root`.
- Compare live state with `systemctl`, `ss`, direct file reads, and the current on-host 1Panel files before trusting older inventory.

## Resources

- [references/data-layout.md](references/data-layout.md)
  Fresh-install data layout, WSL access checks, and normalization rules for `/data/1panel`.
