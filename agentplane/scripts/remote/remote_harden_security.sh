#!/usr/bin/env bash
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive

apt-get update
apt-get install -y --no-install-recommends fail2ban ufw

mkdir -p /etc/ssh/sshd_config.d
cat > /etc/ssh/sshd_config.d/99-hardening.conf <<'EOF'
PasswordAuthentication no
KbdInteractiveAuthentication no
ChallengeResponseAuthentication no
PubkeyAuthentication yes
PermitRootLogin no
MaxAuthTries 3
EOF

sshd -t
systemctl reload ssh

mkdir -p /etc/fail2ban/jail.d
cat > /etc/fail2ban/jail.d/sshd.local <<'EOF'
[sshd]
enabled = true
backend = systemd
port = 22
maxretry = 5
findtime = 10m
bantime = 1h
EOF

systemctl enable --now fail2ban
fail2ban-client restart

ufw --force reset
ufw default deny incoming
ufw default allow outgoing
ufw allow from 0.0.0.0/0 to any port 22 proto tcp
ufw --force enable

echo '===SSHD_EFFECTIVE==='
sshd -T | grep -E 'passwordauthentication|kbdinteractiveauthentication|pubkeyauthentication|permitrootlogin|maxauthtries'
echo '===FAIL2BAN==='
fail2ban-client status sshd
echo '===UFW==='
ufw status verbose
