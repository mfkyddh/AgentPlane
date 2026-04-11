#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
SSH_CONFIG="$REPO_ROOT/secrets/ssh/config"

TARGET_HOST="${1:-prod0-main}"
SSH_USER="${2:-}"
SSH_PORT="${3:-22}"
SSH_KEY="${4:-}"

SSH_ARGS=(-F "$SSH_CONFIG")
if [[ -n "$SSH_USER" ]]; then
  SSH_ARGS+=(-l "$SSH_USER")
fi
if [[ -n "$SSH_KEY" ]]; then
  if [[ ! -f "$SSH_KEY" ]]; then
    echo "SSH key not found: $SSH_KEY" >&2
    exit 1
  fi
  SSH_ARGS+=(-i "$SSH_KEY")
fi

ssh \
  "${SSH_ARGS[@]}" \
  -p "$SSH_PORT" \
  -o StrictHostKeyChecking=accept-new \
  -o BatchMode=yes \
  -o ConnectTimeout=10 \
  "$TARGET_HOST" 'bash -s' <<'REMOTE'
set -euo pipefail

printf 'hostname=%s\n' "$(hostname)"
printf 'kernel=%s\n' "$(uname -srmo)"

if [[ -f /etc/os-release ]]; then
  . /etc/os-release
  printf 'os=%s %s\n' "${NAME:-unknown}" "${VERSION:-}"
fi

printf 'uptime=%s\n' "$(uptime -p 2>/dev/null || true)"
printf 'time=%s\n' "$(date -Is)"
printf 'user=%s\n' "$(id -un)"
printf 'arch=%s\n' "$(uname -m)"
printf 'cpu_model=%s\n' "$(LC_ALL=C lscpu 2>/dev/null | awk -F: '/Model name/ {gsub(/^ +/,"",$2); print $2; exit}')"
printf 'cpu_cores=%s\n' "$(nproc 2>/dev/null || true)"
printf 'memory=%s\n' "$(free -h 2>/dev/null | awk '/Mem:/ {print $2 " total, " $3 " used, " $4 " free"}')"
printf 'disk_root=%s\n' "$(df -h / 2>/dev/null | awk 'NR==2 {print $2 " total, " $3 " used, " $4 " avail"}')"
printf 'ip_addrs=%s\n' "$(hostname -I 2>/dev/null | xargs)"
printf 'sshd=%s\n' "$(ss -ltn 2>/dev/null | awk '/:22 / {print $1 " " $4; found=1} END {if (!found) print "unknown"}')"

if command -v docker >/dev/null 2>&1; then
  docker --version || true
  docker ps --format 'docker_ps={{.Names}} {{.Image}} {{.Status}}' 2>/dev/null || echo 'docker_ps=permission_denied'
fi
REMOTE
