#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$ROOT_DIR/../../.." && pwd)"
ENV_FILE="$REPO_ROOT/secrets/services/openclaw.env"
EXAMPLE_ENV_FILE="$REPO_ROOT/templates/services/openclaw.env.example"
REPO_URL="https://github.com/openclaw/openclaw.git"
OPENCLAW_SOURCE_DIR="/root/work/openclaw"
OPENCLAW_CONFIG_DIR="/data/openclaw/config"
OPENCLAW_WORKSPACE_DIR="/data/openclaw/workspace"
OPENCLAW_GATEWAY_PORT="18789"

fail() {
  echo "ERROR: $*" >&2
  exit 1
}

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    fail "Missing dependency: $1"
  fi
}

ensure_env_file() {
  if [[ -f "$ENV_FILE" ]]; then
    return 0
  fi
  mkdir -p "$(dirname "$ENV_FILE")"
  cp "$EXAMPLE_ENV_FILE" "$ENV_FILE"
  chmod 600 "$ENV_FILE"
  echo "Created $ENV_FILE from template"
}

upsert_env_value() {
  local key="$1"
  local value="$2"
  local tmp
  tmp="$(mktemp)"
  if [[ -f "$ENV_FILE" ]]; then
    awk -F= -v key="$key" '$1 != key { print $0 }' "$ENV_FILE" >"$tmp"
  fi
  printf '%s=%s\n' "$key" "$value" >>"$tmp"
  mv "$tmp" "$ENV_FILE"
}

load_env() {
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
}

ensure_gateway_token() {
  if [[ -n "${OPENCLAW_GATEWAY_TOKEN:-}" && "${OPENCLAW_GATEWAY_TOKEN}" != "change-me-to-a-long-random-token" ]]; then
    return 0
  fi
  require_cmd openssl
  OPENCLAW_GATEWAY_TOKEN="$(openssl rand -hex 32)"
  upsert_env_value "OPENCLAW_GATEWAY_TOKEN" "$OPENCLAW_GATEWAY_TOKEN"
  export OPENCLAW_GATEWAY_TOKEN
  echo "Generated OPENCLAW_GATEWAY_TOKEN in $ENV_FILE"
}

ensure_source_checkout() {
  if [[ -d "$OPENCLAW_SOURCE_DIR/.git" ]]; then
    git -C "$OPENCLAW_SOURCE_DIR" remote get-url origin >/dev/null 2>&1 || fail "Existing OPENCLAW_SOURCE_DIR is not a usable git checkout: $OPENCLAW_SOURCE_DIR"
    echo "Updating existing OpenClaw checkout: $OPENCLAW_SOURCE_DIR"
    git -C "$OPENCLAW_SOURCE_DIR" fetch --depth 1 origin main
    git -C "$OPENCLAW_SOURCE_DIR" checkout FETCH_HEAD
    return 0
  fi

  mkdir -p "$(dirname "$OPENCLAW_SOURCE_DIR")"
  echo "Cloning OpenClaw into $OPENCLAW_SOURCE_DIR"
  git clone --depth 1 "$REPO_URL" "$OPENCLAW_SOURCE_DIR"
}

ensure_data_dirs() {
  sudo mkdir -p "$OPENCLAW_CONFIG_DIR" "$OPENCLAW_WORKSPACE_DIR"
  sudo mkdir -p "$OPENCLAW_CONFIG_DIR/identity" "$OPENCLAW_CONFIG_DIR/agents/main/agent" "$OPENCLAW_CONFIG_DIR/agents/main/sessions"
  sudo chown -R 1000:1000 "$OPENCLAW_CONFIG_DIR" "$OPENCLAW_WORKSPACE_DIR"
}

require_cmd docker
git --version >/dev/null 2>&1 || fail "Missing dependency: git"
docker compose version >/dev/null 2>&1 || fail "Docker Compose is not available"
require_cmd sudo

ensure_env_file
load_env
ensure_gateway_token
ensure_source_checkout
ensure_data_dirs

echo "Building and starting OpenClaw gateway"
docker compose -f "$ROOT_DIR/docker-compose.wsl.yml" up -d --build openclaw-gateway

echo ""
echo "OpenClaw gateway is starting."
echo "Config dir: $OPENCLAW_CONFIG_DIR"
echo "Workspace dir: $OPENCLAW_WORKSPACE_DIR"
echo "Gateway URL: http://127.0.0.1:${OPENCLAW_GATEWAY_PORT}"
echo "Docker network: openclaw_network"
echo "Gateway token: $OPENCLAW_GATEWAY_TOKEN"
echo ""
echo "Recommended next steps:"
echo "  1. Fill at least one model API key in $ENV_FILE"
echo "  2. Check health: docker compose -f $ROOT_DIR/docker-compose.wsl.yml ps"
echo "  3. Run onboarding: docker compose -f $ROOT_DIR/docker-compose.wsl.yml run --rm openclaw-cli onboard --mode local --no-install-daemon"
echo "  4. Run doctor: docker compose -f $ROOT_DIR/docker-compose.wsl.yml run --rm openclaw-cli doctor"
