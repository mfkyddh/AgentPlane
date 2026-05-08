"""Shared test fixture constants.

Only fixture INPUT values (fake domains, IPs, ports, container names) used to
build test inventories, contracts, and compose files.  Do NOT put assertion
expectations here — those belong in the test that asserts them.
"""

from __future__ import annotations

# --- Network fixtures ---
FAKE_HOST_BINDING = "127.0.0.1:18080"
FAKE_CONTAINER_PORT = 8080
FAKE_HEALTHCHECK_PATH = "/health"

# --- Container names ---
CONTAINER_SUB2API = "sub2api-prod"
CONTAINER_POSTGRES = "postgres18-prod"
CONTAINER_REDIS = "redis7-prod"
CONTAINER_MINIO = "minio-prod"
CONTAINER_OPENRESTY = "1panel-openresty-prod"

# --- Domains (RFC 2606 reserved example domains) ---
DOMAIN_TOKEN = "token.example.net"
DOMAIN_RELAY = "relay.example.org"
DOMAIN_SAMPLEAPI = "sampleapi.example.net"

# --- IPs (RFC 5737 TEST-NET) ---
IP_CLOUDFLARE_RECORD = "198.51.100.20"

# --- App identifiers ---
APP_ID_SUB2API = "sub2api"
APP_ID_SAMPLEAPI = "sampleapi"
TARGET_PROD = "prod0-main"
TARGET_WSL = "wsl"

# --- Database defaults ---
PG_DATABASE_PROD = "sub2api_prod0"
PG_USER_PROD = "sub2api_prod0"
REDIS_DB = 1
REDIS_KEY_PREFIX = "sub2api:"
