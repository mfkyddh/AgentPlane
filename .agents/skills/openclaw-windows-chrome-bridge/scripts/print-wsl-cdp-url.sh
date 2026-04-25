#!/usr/bin/env bash
set -euo pipefail

BRIDGE_PORT="${1:-9223}"
GATEWAY_IP="$(ip route show default | sed -n 's/^default via \([^ ]*\).*/\1/p' | head -n 1)"

if [[ -z "${GATEWAY_IP}" ]]; then
  echo "Failed to detect WSL default gateway IP." >&2
  exit 1
fi

CDP_URL="http://${GATEWAY_IP}:${BRIDGE_PORT}"

curl -fsS "${CDP_URL}/json/version" >/dev/null

cat <<EOF
WSL gateway IP: ${GATEWAY_IP}
Bridge port: ${BRIDGE_PORT}
OpenClaw cdpUrl: ${CDP_URL}

JSON snippet:
{
  "browser": {
    "enabled": true,
    "headless": false,
    "defaultProfile": "remote",
    "profiles": {
      "remote": {
        "cdpUrl": "${CDP_URL}",
        "attachOnly": true,
        "color": "#2F855A"
      }
    }
  }
}
EOF
