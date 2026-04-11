#!/usr/bin/env bash
set -euo pipefail

echo '===SSHD_EFFECTIVE==='
sshd -T | grep -E 'passwordauthentication|kbdinteractiveauthentication|pubkeyauthentication|permitrootlogin|maxauthtries'

echo '===FAIL2BAN==='
if command -v fail2ban-client >/dev/null 2>&1; then
  fail2ban-client status sshd || true
else
  echo 'fail2ban-client missing'
fi

echo '===UFW==='
if command -v ufw >/dev/null 2>&1; then
  ufw status verbose || true
else
  echo 'ufw missing'
fi
