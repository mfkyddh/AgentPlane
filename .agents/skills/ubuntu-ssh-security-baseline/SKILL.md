---
name: ubuntu-ssh-security-baseline
description: "Harden Ubuntu or WSL SSH access with a minimal public-facing baseline: enable a default-deny host firewall, allow only the requested SSH port and sources, disable password login, disable root login unless explicitly requested, and enable fail2ban to ban IPs after repeated SSH failures. Use when Codex is asked to secure SSH, turn on UFW, enforce key-only login, or add basic brute-force protection on Ubuntu cloud hosts."
---

# Ubuntu SSH Security Baseline

Apply a lightweight SSH hardening baseline for small Ubuntu servers where resource efficiency matters.

## Workflow

1. Detect the effective remote user, OS version, SSH port, current firewall state, and whether `cloud-init` overrides SSH settings in `/etc/ssh/sshd_config.d/50-cloud-init.conf`.
2. Keep the rule set minimal: use `ufw`, set `default deny incoming`, keep `default allow outgoing`, and allow only the exact SSH port and requested source CIDRs.
3. Prefer key-only login. Set `PasswordAuthentication no`, `KbdInteractiveAuthentication no`, `ChallengeResponseAuthentication no`, `PubkeyAuthentication yes`, and `AuthenticationMethods publickey`.
4. Disable root SSH login unless the user explicitly asks to keep it. Set `PermitRootLogin no` for the hardened baseline.
5. Cap retries with `MaxAuthTries 3` unless the user gave a stricter or looser requirement.
6. Validate SSH config with `sshd -t` before reloading or restarting `ssh`.
7. Install `fail2ban` with `--no-install-recommends` to keep footprint low, then enable the `sshd` jail with the requested threshold. For the common baseline in this repo, use `maxretry = 5`, `findtime = 10m`, and `bantime = 1h`.
8. If `fail2ban` reports a stale socket, remove `/var/run/fail2ban/fail2ban.sock` and restart the service cleanly.
9. Verify the final state with `sshd -T`, `ufw status verbose`, and `fail2ban-client status sshd`.
10. If the host is managed from this repository, update the server inventory and `AGENTS.md` with durable pitfalls discovered during the change.

## Minimal Files To Touch

- `/etc/ssh/sshd_config.d/50-cloud-init.conf` when `cloud-init` still forces `PasswordAuthentication yes`
- `/etc/ssh/sshd_config.d/99-hardening.conf` for the intended final SSH baseline
- `/etc/fail2ban/jail.d/sshd.local` for the SSH brute-force policy

## Verification Checklist

- `sshd -T` shows `passwordauthentication no`
- `sshd -T` shows `authenticationmethods publickey`
- `sshd -T` shows `permitrootlogin no` unless the user explicitly chose otherwise
- `ufw` is active and only the requested SSH port is open for inbound traffic
- `fail2ban-client status sshd` reports the jail as active

## Notes

- On Ubuntu cloud images, `50-cloud-init.conf` can silently override later assumptions; always verify effective SSH settings instead of trusting one file.
- Keep the package footprint small on low-resource hosts by avoiding extra security daemons beyond `ufw` and `fail2ban` unless the user asks for them.
- In this repository's WSL environment, outbound SSH to cloud hosts may already depend on a host-specific entry in `secrets/ssh/config`. Before asking for a new PEM path, check whether a working alias already exists with a PEM under `secrets/ssh/keys/` and a Windows-host proxy such as `ProxyCommand nc -X connect -x 172.25.240.1:7890 %h %p`.
- When the repository already contains a working alias and PEM under `secrets/ssh/keys/`, prefer reusing that tracked path instead of falling back to ad-hoc local key copies.
