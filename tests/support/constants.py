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

# Proxy URLs (localhost bindings used in ingress / onepanel tests)
FAKE_PROXY_8080 = "http://127.0.0.1:8080"
FAKE_PROXY_9090 = "http://127.0.0.1:9090"
FAKE_PROXY_2096 = "http://127.0.0.1:2096"
FAKE_PROXY_3000 = "http://127.0.0.1:3000"
FAKE_PROXY_18080 = "http://127.0.0.1:18080"
FAKE_PROXY_18081 = "http://127.0.0.1:18081"

# App host bindings (non-default ports)
FAKE_BINDING_3000 = "127.0.0.1:3000"
FAKE_BINDING_18081 = "127.0.0.1:18081"

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
DOMAIN_MIGRATED = "migrated.example.com"
DOMAIN_OTHER = "other.example.com"
DOMAIN_KEEP = "keep.example.com"
DOMAIN_NGINX = "nginx.example.net"
DOMAIN_NGINX_COM = "nginx.example.com"
DOMAIN_PROXY = "proxy.example.com"
DOMAIN_MISSING = "missing.example.net"
DOMAIN_RELAY_COM = "relay.example.com"
DOMAIN_A = "a.example.com"
DOMAIN_B = "b.example.com"
DOMAIN_TOKEN_ORG = "token.example.org"
DOMAIN_LANE5 = "lane5.example.com"
DOMAIN_SECOND = "second.example.com"
DOMAIN_OLD = "old.example.com"
DOMAIN_TEST = "test.example.com"
DOMAIN_1PANEL = "1panel.example.com"
DOMAIN_1PANEL_ORG = "1panel.example.org"
DOMAIN_PANEL_NET = "panel.example.net"

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
