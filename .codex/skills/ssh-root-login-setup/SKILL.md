---
name: ssh-root-login-setup
description: Install and configure OpenSSH Server in Ubuntu or WSL, listen on port 22, allow root login, optionally enable password authentication, verify the root account is unlocked, and confirm the daemon is running. Use when Codex is asked to enable SSH access, permit root SSH login, fix a missing sshd service, or make root password login work on a local Ubuntu or WSL machine.
---

# SSH Root Login Setup

Install `openssh-server` when needed, make the SSH daemon listen on the requested port, explicitly configure root login behavior, and verify the result with both `sshd` runtime output and socket state.

## Workflow

1. Detect the current Linux environment, effective user, and whether `/usr/sbin/sshd` and `/etc/ssh/sshd_config` already exist.
2. Install `openssh-server` if `sshd` is missing.
3. Ensure `/run/sshd` exists before starting the service in WSL or minimal Ubuntu images.
4. Set `Port 22` unless the user requested another port.
5. Set `PermitRootLogin yes` when the user explicitly wants root SSH access.
6. If password login is required, set `PasswordAuthentication yes`, then verify `root` is not locked with `passwd -S root`.
7. If the user provided a password, apply it with `chpasswd`.
8. Restart `ssh` and verify `sshd -T` reports the expected `port`, `permitrootlogin`, and `passwordauthentication` values.
9. Verify `ss -ltnp` shows `sshd` listening on the expected port and summarize any remaining blockers such as a locked `root` account.

## Command Pattern

Prefer Ubuntu or WSL commands with a single Bash payload:

```bash
wsl -d Ubuntu -- bash -lc '...'
```

Inspect the current state:

```bash
command -v sshd || true
grep -nE "^(#\\s*)?(PermitRootLogin|PasswordAuthentication|Port)\\b" /etc/ssh/sshd_config || true
passwd -S root || true
```

Install and prepare OpenSSH Server:

```bash
apt-get update
apt-get install -y openssh-server
install -d -m 0755 /run/sshd
ssh-keygen -A
```

Update `sshd_config` idempotently:

```bash
sed -i "s/^#\\?PermitRootLogin.*/PermitRootLogin yes/" /etc/ssh/sshd_config
sed -i "s/^#\\?PasswordAuthentication.*/PasswordAuthentication yes/" /etc/ssh/sshd_config
sed -i "s/^#\\?Port.*/Port 22/" /etc/ssh/sshd_config
```

Append a setting if it does not exist yet:

```bash
printf "\nPermitRootLogin yes\n" >> /etc/ssh/sshd_config
```

Set the root password when the user explicitly supplied one:

```bash
printf "root:<password>\n" | chpasswd
```

Restart and verify:

```bash
systemctl restart ssh || service ssh restart
sshd -T | grep -E "^(port|permitrootlogin|passwordauthentication) "
ss -ltnp | grep ":22\\b"
```

## Notes

- In fresh Ubuntu or WSL installs, `root` is often locked even after `PermitRootLogin yes`; `passwd -S root` must show `P` for password login to work.
- If the user only wants key-based root access, keep `PermitRootLogin yes` or switch to `prohibit-password` depending on the request, and do not enable `PasswordAuthentication`.
- PowerShell to `bash -lc` quoting is fragile. Prefer a single-quoted Bash payload and absolute Linux paths when commands become long.
- Report the exact verified values from `sshd -T` instead of assuming the file contents were accepted.