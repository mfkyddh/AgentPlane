#!/usr/bin/env bash
set -euo pipefail

rm -f /var/run/fail2ban/fail2ban.sock
systemctl restart fail2ban
systemctl enable fail2ban

ufw --force reset
ufw default deny incoming
ufw default allow outgoing
ufw allow from 0.0.0.0/0 to any port 22 proto tcp
ufw --force enable

echo '===FAIL2BAN==='
systemctl is-active fail2ban
fail2ban-client status sshd
echo '===UFW==='
ufw status verbose
