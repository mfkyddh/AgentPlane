#!/usr/bin/env bash
set -euo pipefail

if grep -q '^PasswordAuthentication yes' /etc/ssh/sshd_config.d/50-cloud-init.conf 2>/dev/null; then
  sed -i 's/^PasswordAuthentication yes/PasswordAuthentication no/' /etc/ssh/sshd_config.d/50-cloud-init.conf
fi

cat > /etc/ssh/sshd_config.d/99-hardening.conf <<'EOF'
PasswordAuthentication no
KbdInteractiveAuthentication no
ChallengeResponseAuthentication no
PubkeyAuthentication yes
AuthenticationMethods publickey
PermitRootLogin no
MaxAuthTries 3
EOF

sshd -t
systemctl restart ssh

echo '===SSHD_EFFECTIVE==='
sshd -T | grep -E 'passwordauthentication|kbdinteractiveauthentication|pubkeyauthentication|authenticationmethods|permitrootlogin|maxauthtries'
