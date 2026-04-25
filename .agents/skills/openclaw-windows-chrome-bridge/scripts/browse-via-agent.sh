#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <url>" >&2
  exit 1
fi

URL="$1"
AGENT_ID="${OPENCLAW_AGENT_ID:-main}"
PROFILE_NAME="${OPENCLAW_BROWSER_PROFILE:-remote}"
TIMEOUT_SECONDS="${OPENCLAW_AGENT_TIMEOUT_SECONDS:-180}"
MAX_ATTEMPTS="${OPENCLAW_BROWSE_AGENT_ATTEMPTS:-2}"
SESSION_ID="${OPENCLAW_AGENT_SESSION_ID:-browse-remote-$(date +%Y%m%d%H%M%S)}"
SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPAIR_SCRIPT="${SKILL_DIR}/repair-browser-stack.sh"
OPENCLAW_BASE_CMD=(openclaw --log-level silent)

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 is required for agent result parsing." >&2
  exit 1
fi

ensure_remote_ready() {
  local status_json
  if status_json="$("${OPENCLAW_BASE_CMD[@]}" browser status --browser-profile "${PROFILE_NAME}" --json 2>/dev/null)"; then
    if printf '%s' "${status_json}" | grep -q '"running": true' && \
       printf '%s' "${status_json}" | grep -q '"cdpReady": true' && \
       printf '%s' "${status_json}" | grep -q '"cdpHttp": true'; then
      return 0
    fi
  fi

  bash "${REPAIR_SCRIPT}" >/tmp/openclaw-repair-browser-stack.log
}

agent_prompt() {
  cat <<EOF
使用 Browse 工具和 browser profile ${PROFILE_NAME} 打开 ${URL}。先检查 browser status，再打开页面，然后告诉我页面标题、当前 URL，以及是否遇到登录页、验证码或权限限制。不要切换到别的 profile；如果失败，原样返回错误。
EOF
}

agent_result_ok() {
  local response_file="$1"
  python3 - "$URL" "${response_file}" <<'PY'
import json
import sys

target_url = sys.argv[1]
response_file = sys.argv[2]
with open(response_file, "r", encoding="utf-8") as fh:
    data = json.load(fh)
payloads = data.get("result", {}).get("payloads", [])
text = "\n".join(p.get("text", "") for p in payloads if isinstance(p, dict))
ok = data.get("status") == "ok" and target_url in text and ("成功" in text or "success" in text.lower())
sys.exit(0 if ok else 1)
PY
}

last_response_file=""

for attempt in $(seq 1 "${MAX_ATTEMPTS}"); do
  ensure_remote_ready

  response_file="$(mktemp)"
  last_response_file="${response_file}"
  if "${OPENCLAW_BASE_CMD[@]}" agent --agent "${AGENT_ID}" --session-id "${SESSION_ID}" --message "$(agent_prompt)" --thinking medium --timeout "${TIMEOUT_SECONDS}" --json >"${response_file}" 2>/tmp/openclaw-browse-agent.err; then
    if agent_result_ok "${response_file}"; then
      cat "${response_file}"
      exit 0
    fi
  fi

  if [[ "${attempt}" -lt "${MAX_ATTEMPTS}" ]]; then
    bash "${REPAIR_SCRIPT}" >/tmp/openclaw-repair-browser-stack.log
  fi
done

echo "Browse-via-agent did not succeed after ${MAX_ATTEMPTS} attempt(s)." >&2
if [[ -n "${last_response_file}" && -f "${last_response_file}" ]]; then
  echo "Last agent response:" >&2
  cat "${last_response_file}" >&2
fi
echo "Last agent stderr:" >&2
cat /tmp/openclaw-browse-agent.err >&2 || true
echo "Recent gateway log tail:" >&2
journalctl --user -u openclaw-gateway -n 80 --no-pager >&2 || true
exit 1
