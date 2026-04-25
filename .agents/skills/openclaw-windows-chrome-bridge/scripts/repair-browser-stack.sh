#!/usr/bin/env bash
set -euo pipefail

PROFILE_NAME="${OPENCLAW_BROWSER_PROFILE:-remote}"
BRIDGE_PORT="${OPENCLAW_BRIDGE_PORT:-9223}"
SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WINDOWS_START_SCRIPT="${SKILL_DIR}/start-chrome-bridge.ps1"
OPENCLAW_CONFIG_PATH="${OPENCLAW_CONFIG_PATH:-$HOME/.openclaw/openclaw.json}"
OPENCLAW_BASE_CMD=(openclaw --log-level silent)

if [[ ! -f "${OPENCLAW_CONFIG_PATH}" ]]; then
  echo "OpenClaw config not found: ${OPENCLAW_CONFIG_PATH}" >&2
  exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 is required for JSON config repair." >&2
  exit 1
fi

GATEWAY_IP="$(ip route show default | sed -n 's/^default via \([^ ]*\).*/\1/p' | head -n 1)"
if [[ -z "${GATEWAY_IP}" ]]; then
  echo "Failed to detect the WSL default gateway IP." >&2
  exit 1
fi

DESIRED_CDP_URL="http://${GATEWAY_IP}:${BRIDGE_PORT}"
WINDOWS_START_SCRIPT_WIN="$(wslpath -w "${WINDOWS_START_SCRIPT}")"

echo "Ensuring Windows Chrome debug bridge..."
powershell.exe -ExecutionPolicy Bypass -File "${WINDOWS_START_SCRIPT_WIN}" >/tmp/openclaw-start-chrome-bridge.log 2>&1 || {
  cat /tmp/openclaw-start-chrome-bridge.log >&2
  exit 1
}

echo "Updating OpenClaw browser profile '${PROFILE_NAME}' to ${DESIRED_CDP_URL}..."
python3 - "${OPENCLAW_CONFIG_PATH}" "${PROFILE_NAME}" "${DESIRED_CDP_URL}" <<'PY'
import json
import pathlib
import shutil
import sys

config_path = pathlib.Path(sys.argv[1])
profile_name = sys.argv[2]
desired_cdp_url = sys.argv[3]

with config_path.open("r", encoding="utf-8") as fh:
    data = json.load(fh)

browser = data.setdefault("browser", {})
browser["enabled"] = True
browser.setdefault("headless", False)
browser["defaultProfile"] = profile_name
profiles = browser.setdefault("profiles", {})
profile = profiles.setdefault(profile_name, {})
profile["cdpUrl"] = desired_cdp_url
profile["attachOnly"] = True
profile.setdefault("color", "#2F855A")

backup_path = config_path.with_name(config_path.name + ".auto-browser-backup")
shutil.copy2(config_path, backup_path)

with config_path.open("w", encoding="utf-8") as fh:
    json.dump(data, fh, ensure_ascii=True, indent=2)
    fh.write("\n")
PY

echo "Validating config and restarting OpenClaw gateway..."
"${OPENCLAW_BASE_CMD[@]}" config validate >/tmp/openclaw-config-validate.log
systemctl --user restart openclaw-gateway

for _ in $(seq 1 20); do
  if status_json="$("${OPENCLAW_BASE_CMD[@]}" browser status --browser-profile "${PROFILE_NAME}" --json 2>/tmp/openclaw-browser-status.err)"; then
    if printf '%s' "${status_json}" | grep -q '"running": true' && \
       printf '%s' "${status_json}" | grep -q '"cdpReady": true' && \
       printf '%s' "${status_json}" | grep -q '"cdpHttp": true'; then
      echo "${status_json}"
      exit 0
    fi
  fi
  sleep 2
done

echo "Browser stack repair did not reach a healthy remote profile." >&2
echo "Last browser status stderr:" >&2
cat /tmp/openclaw-browser-status.err >&2 || true
echo "Recent gateway log tail:" >&2
journalctl --user -u openclaw-gateway -n 80 --no-pager >&2 || true
exit 1
